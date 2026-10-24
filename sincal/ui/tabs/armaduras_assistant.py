"""Tablero guiado para el flujo híbrido del generador de armaduras.

El componente no conoce AutoCAD, ZWCAD ni el calculo estructural. Recibe un
modelo de estados y callbacks, de modo que ``TabArmaduras`` pueda adoptarlo de
forma gradual sin trasladar lógica CAD a la interfaz.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Mapping

import customtkinter as ctk
import ttkbootstrap as ttk

from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_ACENTO_HOVER,
    COLOR_BORDE,
    COLOR_ERROR,
    COLOR_EXITO,
    COLOR_FONDO,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
    RADIO_CONTROL,
)
from sincal.ui.widgets import ShadowButton
from sincal.rebar.catalog import BRIDGE_REBAR_CATALOG


STATUS_PENDING = "pending"
STATUS_DETECTED = "detected"
STATUS_NEEDS_INPUT = "needs_input"
STATUS_READY = "ready"
STATUS_GENERATED = "generated"
STATUS_ERROR = "error"
STATUS_NOT_APPLICABLE = "not_applicable"

STATUS_LABELS = {
    STATUS_PENDING: "Pendiente",
    STATUS_DETECTED: "Detectado",
    STATUS_NEEDS_INPUT: "Requiere revision",
    STATUS_READY: "Listo",
    STATUS_GENERATED: "Generado",
    STATUS_ERROR: "Error",
    STATUS_NOT_APPLICABLE: "No aplica",
}


@dataclass(frozen=True)
class StructuralElement:
    """Estado visible de un elemento o agrupador del puente."""

    id: str
    name: str
    parent_id: str | None = None
    status: str = STATUS_PENDING
    description: str = ""
    layers: tuple[str, ...] = ()
    optional: bool = False
    message: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in STATUS_LABELS:
            raise ValueError(f"Estado estructural desconocido: {self.status}")
        if not self.id.strip():
            raise ValueError("El identificador del elemento no puede estar vacio.")


class ArmaturesAssistantModel:
    """Modelo puro del tablero; no necesita una raiz Tk para probarse."""

    def __init__(self, elements: Iterable[StructuralElement] = ()):
        self._elements: dict[str, StructuralElement] = {}
        self.set_elements(elements)

    @property
    def elements(self) -> tuple[StructuralElement, ...]:
        return tuple(self._elements.values())

    def set_elements(self, elements: Iterable[StructuralElement]) -> None:
        indexed: dict[str, StructuralElement] = {}
        for element in elements:
            if element.id in indexed:
                raise ValueError(f"Elemento estructural duplicado: {element.id}")
            indexed[element.id] = element
        for element in indexed.values():
            if element.parent_id is not None and element.parent_id not in indexed:
                raise ValueError(
                    f"El padre {element.parent_id!r} de {element.id!r} no existe."
                )
            seen = {element.id}
            parent_id = element.parent_id
            while parent_id is not None:
                if parent_id in seen:
                    raise ValueError(f"Jerarquía cíclica en {element.id!r}.")
                seen.add(parent_id)
                parent_id = indexed[parent_id].parent_id
        self._elements = indexed

    def get(self, element_id: str) -> StructuralElement:
        return self._elements[element_id]

    def roots(self) -> tuple[StructuralElement, ...]:
        return tuple(e for e in self._elements.values() if e.parent_id is None)

    def children(self, element_id: str) -> tuple[StructuralElement, ...]:
        return tuple(e for e in self._elements.values() if e.parent_id == element_id)

    def update(self, element_id: str, **changes) -> StructuralElement:
        current = self.get(element_id)
        updated = replace(current, **changes)
        self._elements[element_id] = updated
        return updated

    def status_counts(self) -> dict[str, int]:
        return dict(Counter(element.status for element in self._elements.values()))

    def ready_elements(self) -> tuple[StructuralElement, ...]:
        return tuple(e for e in self._elements.values() if e.status == STATUS_READY)


def default_bridge_elements() -> tuple[StructuralElement, ...]:
    """Jerarquía inicial del tablero, ampliable con instancias desde el JSON."""

    items: list[StructuralElement] = []

    def add(identifier, name, parent=None, *, optional=False, description=""):
        items.append(StructuralElement(
            identifier, name, parent_id=parent, optional=optional,
            description=description,
        ))

    add("abutments", "1 · Estribos")
    for side_id, side_name in (("entry", "Estribo de entrada"), ("exit", "Estribo de salida")):
        root = f"abutment.{side_id}"
        add(root, side_name, "abutments")
        add(f"{root}.footing", "Zapata", root)
        add(f"{root}.front_wall", "Muro frontal", root)
        add(f"{root}.back_wall", "Muro espaldar", root)
        add(f"{root}.left_wing", "Ala izquierda", root)
        add(f"{root}.right_wing", "Ala derecha", root)
        add(f"{root}.pile", "Pilotes", root, optional=True)
        add(f"{root}.counterfort", "Contrafuertes", root, optional=True)

    add("piers", "2 · Cepas")
    add("piers.headstock", "Cabezal", "piers")
    add("piers.pile", "Pilotes", "piers")
    add("piers.stop", "Topes sísmicos", "piers")
    add("piers.bracket", "Consolas", "piers", optional=True)

    add("beams", "3 · Vigas")
    add("crossbeams", "4 · Travesaños")
    add("crossbeams.support", "Sobre apoyos", "crossbeams")
    add("crossbeams.intermediate", "Intermedios", "crossbeams")
    add("slab", "5 · Losa")
    return tuple(items)


_RECIPE_LABELS = {
    "parallel_bars": "Barras paralelas",
    "orthogonal_mesh": "Malla ortogonal",
    "u_bars": "Barras en U",
    "longitudinal_bars": "Barras longitudinales",
    "closed_stirrups": "Estribos cerrados",
    "transverse_ties": "Amarras transversales",
    "face_bars": "Barras de cara",
    "edge_bars": "Barras de borde",
    "additional_bars": "Refuerzos adicionales",
}


def project_bridge_elements(data: Mapping | None) -> tuple[StructuralElement, ...]:
    """Construye el árbol real del proyecto usando el catálogo declarativo.

    Se incluyen también los elementos opcionales ausentes para que el dibujante
    entienda por qué no participan; quedan en gris como ``No aplica``.
    """

    project = data if isinstance(data, Mapping) else {}
    result: list[StructuralElement] = []
    for structure in BRIDGE_REBAR_CATALOG.structures:
        root_id = f"structure:{structure.key}"
        instances = BRIDGE_REBAR_CATALOG.resolve_instances(structure.key, project)
        root_status = STATUS_PENDING if instances else STATUS_NOT_APPLICABLE
        result.append(StructuralElement(
            root_id,
            f"{structure.folder} · {structure.label}",
            status=root_status,
            description=f"Familia estructural {structure.label.lower()} del proyecto activo.",
            message=(
                f"{len(instances)} instancia(s) identificada(s) desde el JSON."
                if instances else "El JSON no declara instancias de esta familia."
            ),
            metadata={"structure_key": structure.key},
        ))
        for instance in instances:
            instance_id = f"instance:{structure.key}:{instance.key}"
            result.append(StructuralElement(
                instance_id,
                instance.label,
                parent_id=root_id,
                status=STATUS_PENDING,
                description="Instancia estructural identificada desde el proyecto.",
                metadata={
                    "structure_key": structure.key,
                    "instance_key": instance.key,
                },
            ))
            for specification in BRIDGE_REBAR_CATALOG.elements_for(structure.key):
                present = specification.presence.resolve(project, instance.key)
                status = STATUS_PENDING if present else STATUS_NOT_APPLICABLE
                message = "Pendiente de analizar en el dibujo activo."
                if not present:
                    message = "El JSON no activa este elemento opcional."
                elif specification.definition_pending:
                    status = STATUS_NEEDS_INPUT
                    message = "Falta definir las capas de moldaje de este elemento."
                recipes = ", ".join(
                    _RECIPE_LABELS.get(recipe.value, recipe.value)
                    for recipe in specification.recipes
                )
                element_id = (
                    f"element:{structure.key}:{instance.key}:{specification.key}"
                )
                result.append(StructuralElement(
                    element_id,
                    specification.label,
                    parent_id=instance_id,
                    status=status,
                    description=(
                        "Las capas proponen las vistas; la selección CAD confirma "
                        "la instancia antes de aplicar una receta."
                    ),
                    layers=specification.layer_names,
                    optional=specification.optional,
                    message=message,
                    metadata={
                        "structure_key": structure.key,
                        "instance_key": instance.key,
                        "element_key": specification.key,
                        "recetas": recipes or "Pendientes de definición",
                    },
                ))
    return tuple(result)


@dataclass(frozen=True)
class ArmaturesAssistantCallbacks:
    """Acciones que el controlador real inyecta en el tablero."""

    prepare_drawing: Callable[[], None] = lambda: None
    analyze_moldajes: Callable[[], None] = lambda: None
    generate_ready: Callable[[], None] = lambda: None
    select_element: Callable[[StructuralElement], None] = lambda _element: None


def _resolved_color(value):
    if isinstance(value, (tuple, list)):
        return value[1 if ctk.get_appearance_mode() == "Dark" else 0]
    return value


class ArmaturesAssistantDashboard(ctk.CTkFrame):
    """Tablero de reconocimiento, revisión y generación por estados."""

    def __init__(
        self,
        master,
        model: ArmaturesAssistantModel | None = None,
        callbacks: ArmaturesAssistantCallbacks | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=COLOR_FONDO, corner_radius=0, **kwargs)
        self.model = model or ArmaturesAssistantModel(default_bridge_elements())
        self.callbacks = callbacks or ArmaturesAssistantCallbacks()
        self._project_summary = "Proyecto: ninguno"
        self._drawing_summary = "Dibujo activo: no detectado"
        self._units_summary = "Unidades: sin verificar"
        self._session_summary = "Sesión: sin guardar"
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        heading = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        heading.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 8))
        ctk.CTkLabel(
            heading, text="ASISTENTE DE ARMADURAS", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(anchor="w")
        ctk.CTkLabel(
            heading,
            text="Reconoce moldajes, resuelve excepciones y genera los elementos listos.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(anchor="w", pady=(2, 0))

        summary = ctk.CTkFrame(
            self, fg_color="transparent", corner_radius=0,
            border_width=1, border_color=COLOR_BORDE,
        )
        summary.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        summary.grid_columnconfigure((0, 1), weight=1)
        self.project_label = ctk.CTkLabel(
            summary, text=self._project_summary, font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO, anchor="w",
        )
        self.project_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 2))
        self.drawing_label = ctk.CTkLabel(
            summary, text=self._drawing_summary, font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO, anchor="w",
        )
        self.drawing_label.grid(row=0, column=1, sticky="ew", padx=12, pady=(9, 2))
        self.units_label = ctk.CTkLabel(
            summary, text=self._units_summary, font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.units_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 9))
        self.session_label = ctk.CTkLabel(
            summary, text=self._session_summary, font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.session_label.grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 9))

        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        content.grid_columnconfigure(0, weight=5, minsize=270)
        content.grid_columnconfigure(1, weight=4, minsize=250)
        content.grid_rowconfigure(0, weight=1)

        tree_panel = self._panel(content, "ESTRUCTURA Y ESTADO")
        tree_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tree_panel.grid_rowconfigure(1, weight=1)
        tree_panel.grid_columnconfigure(0, weight=1)
        self.progress_label = ctk.CTkLabel(
            tree_panel, text="", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.progress_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        self.tree = ttk.Treeview(
            tree_panel, columns=("status",), show="tree headings",
            selectmode="browse", bootstyle="secondary",
        )
        self.tree.heading("#0", text="Elemento", anchor="w")
        self.tree.heading("status", text="Estado", anchor="w")
        self.tree.column("#0", width=210, minwidth=150, stretch=True)
        self.tree.column("status", width=125, minwidth=105, stretch=False)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))
        scroll = ttk.Scrollbar(tree_panel, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 10))
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection)

        detail = self._panel(content, "ELEMENTO SELECCIONADO")
        detail.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        detail.grid_columnconfigure(0, weight=1)
        self.element_name = ctk.CTkLabel(
            detail, text="Selecciona un elemento", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA, anchor="w",
        )
        self.element_name.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 2))
        self.element_status = ctk.CTkLabel(
            detail, text="", font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.element_status.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.element_description = ctk.CTkLabel(
            detail, text="", font=FUENTE_NORMAL, text_color=COLOR_TEXTO,
            justify="left", anchor="nw", wraplength=520,
        )
        self.element_description.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkLabel(
            detail, text="CAPAS O MOLDAJES", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=14)
        self.element_layers = ctk.CTkLabel(
            detail, text="Sin capas asignadas", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO, justify="left", anchor="nw", wraplength=520,
        )
        self.element_layers.grid(row=4, column=0, sticky="ew", padx=14, pady=(2, 12))
        ctk.CTkLabel(
            detail, text="OBSERVACION", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        ).grid(row=5, column=0, sticky="ew", padx=14)
        self.element_message = ctk.CTkLabel(
            detail, text="Aún no se ha analizado este elemento.", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO_SUAVE, justify="left", anchor="nw", wraplength=520,
        )
        self.element_message.grid(row=6, column=0, sticky="nsew", padx=14, pady=(2, 14))
        detail.grid_rowconfigure(6, weight=1)
        detail.bind("<Configure>", self._resize_detail_wrap, add="+")

        actions = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        self.prepare_button = ShadowButton(
            actions, text="Preparar dibujo", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=RADIO_CONTROL, command=self.callbacks.prepare_drawing,
        )
        self.prepare_button.pack(side="left")
        self.analyze_button = ShadowButton(
            actions, text="Analizar moldajes", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=RADIO_CONTROL, command=self.callbacks.analyze_moldajes,
        )
        self.analyze_button.pack(side="left", padx=(8, 0))
        self.generate_button = ShadowButton(
            actions, text="Revisar y generar", font=FUENTE_NORMAL,
            fg_color=COLOR_ACENTO, hover_color=COLOR_ACENTO_HOVER,
            corner_radius=RADIO_CONTROL, command=self.callbacks.generate_ready,
        )
        self.generate_button.pack(side="right")

        self._configure_status_tags()

    def _resize_detail_wrap(self, event):
        """Adapta los textos del detalle al ancho realmente disponible."""
        wrap = max(160, int(event.width) - 32)
        for label in (
            self.element_description, self.element_layers, self.element_message,
        ):
            label.configure(wraplength=wrap)

    @staticmethod
    def _panel(parent, title):
        label = ttk.Label(parent, text=title, style="SincalLabelframeTitle.TLabel")
        return ttk.Labelframe(parent, labelwidget=label, bootstyle="secondary")

    def _configure_status_tags(self):
        self.tree.tag_configure(STATUS_READY, foreground=_resolved_color(COLOR_EXITO))
        self.tree.tag_configure(STATUS_GENERATED, foreground=_resolved_color(COLOR_EXITO))
        self.tree.tag_configure(STATUS_NEEDS_INPUT, foreground=_resolved_color(COLOR_MOSTAZA))
        self.tree.tag_configure(STATUS_ERROR, foreground=_resolved_color(COLOR_ERROR))
        self.tree.tag_configure(STATUS_NOT_APPLICABLE, foreground=_resolved_color(COLOR_TEXTO_SUAVE))

    def set_summary(
        self,
        *,
        project: str | None = None,
        drawing: str | None = None,
        units: str | None = None,
        session: str | None = None,
    ) -> None:
        if project is not None:
            self._project_summary = project
            self.project_label.configure(text=project)
        if drawing is not None:
            self._drawing_summary = drawing
            self.drawing_label.configure(text=drawing)
        if units is not None:
            self._units_summary = units
            self.units_label.configure(text=units)
        if session is not None:
            self._session_summary = session
            self.session_label.configure(text=session)

    def set_elements(self, elements: Iterable[StructuralElement]) -> None:
        self.model.set_elements(elements)
        self.refresh()

    def update_element(self, element_id: str, **changes) -> StructuralElement:
        updated = self.model.update(element_id, **changes)
        self.refresh(preferred_selection=element_id)
        return updated

    def refresh(self, preferred_selection: str | None = None) -> None:
        selection = preferred_selection
        if selection is None and self.tree.selection():
            selection = self.tree.selection()[0]
        self.tree.delete(*self.tree.get_children())
        pending = list(self.model.elements)
        inserted: set[str] = set()
        while pending:
            progressed = False
            for element in pending[:]:
                parent = element.parent_id or ""
                if parent and parent not in inserted:
                    continue
                self.tree.insert(
                    parent, "end", iid=element.id, text=element.name,
                    values=(STATUS_LABELS[element.status],),
                    tags=(element.status,), open=element.parent_id is None,
                )
                inserted.add(element.id)
                pending.remove(element)
                progressed = True
            if not progressed:
                break

        counts = self.model.status_counts()
        ready = counts.get(STATUS_READY, 0)
        generated = counts.get(STATUS_GENERATED, 0)
        review = counts.get(STATUS_NEEDS_INPUT, 0) + counts.get(STATUS_ERROR, 0)
        self.progress_label.configure(
            text=f"{ready} listos · {generated} generados · {review} por revisar"
        )
        self.generate_button.configure(state="normal" if ready else "disabled")
        if selection and self.tree.exists(selection):
            self.tree.selection_set(selection)
            self.tree.see(selection)
            self._show_element(self.model.get(selection))
        elif self.model.roots():
            first = self.model.roots()[0]
            self.tree.selection_set(first.id)
            self._show_element(first)

    def selected_element(self) -> StructuralElement | None:
        selection = self.tree.selection()
        return self.model.get(selection[0]) if selection else None

    def _on_tree_selection(self, _event=None):
        element = self.selected_element()
        if element is None:
            return
        self._show_element(element)
        self.callbacks.select_element(element)

    def _show_element(self, element: StructuralElement):
        optional = " · Opcional" if element.optional else ""
        self.element_name.configure(text=element.name)
        self.element_status.configure(
            text=f"{STATUS_LABELS[element.status]}{optional}",
            text_color=self._status_color(element.status),
        )
        self.element_description.configure(
            text=element.description or "Elemento estructural del proyecto activo."
        )
        self.element_layers.configure(
            text=", ".join(element.layers) if element.layers else "Sin capas asignadas"
        )
        metadata = "\n".join(f"{key}: {value}" for key, value in element.metadata.items())
        message = element.message or "Aún no se ha analizado este elemento."
        if metadata:
            message = f"{message}\n\n{metadata}"
        self.element_message.configure(text=message)

    @staticmethod
    def _status_color(status):
        if status in (STATUS_READY, STATUS_GENERATED):
            return COLOR_EXITO
        if status == STATUS_ERROR:
            return COLOR_ERROR
        if status == STATUS_NEEDS_INPUT:
            return COLOR_MOSTAZA
        return COLOR_TEXTO_SUAVE
