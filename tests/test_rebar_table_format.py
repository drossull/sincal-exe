"""Migration must never replace the table or overwrite linked data/identities."""
from sincal.web.rebar import defaults, domain
from sincal.rebar.model import build_zapata_schedule
from sincal.cad.rebar_marks import build_marks_support
from tests.test_rebar_marks_cad import lisp_forms


def emitted():
    geometry, cover, rules = domain(defaults())
    return build_marks_support(build_zapata_schedule(geometry, cover, rules), rules, 'entrada')


def form(source, name):
    return next(item for item in lisp_forms(source) if item.startswith(f'(defun {name} '))


def test_only_the_owned_exact_legacy_signature_can_trigger_format_changes():
    source = emitted()
    guard = form(source, 'srb:legacy-table-p')
    assert '(equal (srb:owner table) srb:scope)' in guard
    assert '(strcat "ARMADURAS " srb:scope)' in guard
    assert '\'("MARCA" "CANTIDAD" "DIAMETRO" "SEPARACION")' in guard
    assert '(equal (vla-GetText table 1 column) header)' in guard
    migration = form(source, 'srb:restore-generated-format')
    assert migration.index('(srb:legacy-table-p table)') < migration.index('(srb:copy-table-template)')
    sync = form(source, 'srb:sync-table')
    assert sync.index('(srb:preflight') < sync.index('(srb:adopt-rows)') < sync.index('(srb:restore-generated-format')
    assert sync.index('(vla-SetText') < sync.index('(srb:restore-generated-format') < sync.index('(srb:register')
    assert '(srb:template-managed-p table)' in migration
    assert 'SINCAL_REBAR_TABLE_FORMAT_V1' in form(source, 'srb:template-managed-p')


def test_migration_keeps_table_identity_rows_data_and_link_metadata():
    source = emitted()
    formatting = form(source, 'srb:apply-table-format') + form(source, 'srb:copy-cell-format')
    for forbidden in ('vla-Delete', 'vla-InsertRows', 'SetCustomData', 'srb:register', 'SCM:EnsureID', 'entmod', 'entdel'):
        assert forbidden not in formatting
    writes = [line.strip() for line in formatting.splitlines() if '(vla-SetText ' in line]
    assert len(writes) == 2
    assert all(line.startswith(('(vla-SetText table 0 0', '(vla-SetText table 1 column')) for line in writes)
    migration = form(source, 'srb:restore-generated-format')
    assert '(vla-Delete model)' in migration
    assert '(vla-Delete table)' not in migration
    assert '(vl-catch-all-apply \'srb:apply-table-format (list table model))' in migration
    assert '(/ 10.0 ratio)' in migration
    assert '(srb:clear-template-data' not in migration
    formatting = form(source, 'srb:apply-table-format')
    assert formatting.index('(vla-SetText') < formatting.index('(srb:copy-cell-format') < formatting.index('(vla-SetRowHeight')
