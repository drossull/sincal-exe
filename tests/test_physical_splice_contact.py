"""Contact laps have real adjacent axes without changing fabricated steel."""
from collections import defaultdict
from dataclasses import replace
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, RemovedPiece, ZapataGeometry, default_zapata_rules, lap_length_cm
from sincal.rebar.splices import physical_laps


@pytest.mark.parametrize('skew',(0,-8,8,-12,12,-30,30))
@pytest.mark.parametrize('width',(1159.6,2300,3500))
def test_every_real_lap_has_tangent_axes_and_exact_axial_coverage(skew,width):
    assembly=build_footing_assembly(ZapataGeometry.from_centimetres(750,width,150,skew),
                                  Cover.from_centimetres(7.5,5,5),default_zapata_rules())
    assert assembly.is_valid,assembly.schedule.issues
    pieces={bar.id:bar for bar in assembly.bars}
    runs=defaultdict(list)
    for bar in assembly.bars:
        runs[bar.placement_id].append(bar)
    laps=physical_laps(assembly.bars)
    assert len(laps)==sum(len(run)-1 for run in runs.values())
    for lap in laps:
        owner,partner=pieces[lap.piece_id],pieces[lap.partner_id]
        diameter=(owner.diameter_mm+partner.diameter_mm)/2000
        assert lap.length_cm==pytest.approx(lap_length_cm(owner.diameter_mm))
        assert lap.axis_distance_m==pytest.approx(diameter)
        for a,b in ((lap.start_m,lap.partner_start_m),(lap.end_m,lap.partner_end_m)):
            assert math.dist(a,b)==pytest.approx(diameter)
            assert sum((x-y)*u for x,y,u in zip(a,b,owner.axis_u))==pytest.approx(0,abs=1e-9)
        assert owner.origin_m!=partner.origin_m
        assert owner.axis_u==partner.axis_u and owner.axis_v==partner.axis_v
    # Fabrication values remain lengths along the actual piece, not distances
    # diagonally between the ends of two different contact axes.
    for bar in assembly.bars:
        exact=sum(math.dist(a,b) if abs(bulge)<1e-12 else
                  math.dist(a,b)*abs(4*math.atan(bulge))/(2*math.sin(abs(2*math.atan(bulge))))
                  for a,b,bulge in zip(bar.vertices_m,bar.vertices_m[1:],bar.bulges))*100
        assert exact==pytest.approx(bar.developed_length_cm,abs=1e-7)
        assert bar.length_cm==math.ceil(exact-1e-8)
        assert bar.length_cm<=1200
    assert sum(mark.quantity for mark in assembly.schedule.marks)==len(assembly.bars)
    assert sum(mark.total_length_cm for mark in assembly.schedule.marks)==sum(bar.length_cm for bar in assembly.bars)


def test_missing_middle_piece_does_not_join_separated_same_lane_pieces():
    assembly=build_footing_assembly(ZapataGeometry.from_centimetres(750,2300,150),
                                  Cover.from_centimetres(7.5,5,5),default_zapata_rules())
    run=[bar for bar in assembly.bars if bar.placement_id=='mesh_x:superior:0']
    assert len(run)==3
    assert run[0].origin_m==run[2].origin_m
    assert len(physical_laps(run))==2
    assert physical_laps((run[0],run[2]))==()


def test_parallel_bars_that_do_not_touch_cannot_claim_a_lap():
    assembly=build_footing_assembly(ZapataGeometry.from_centimetres(750,1159.6,150),
                                  Cover.from_centimetres(7.5,5,5),default_zapata_rules())
    run=[bar for bar in assembly.bars if bar.placement_id=='mesh_x:superior:0']
    initial,continuation=run
    shift=tuple(a-b for a,b in zip(initial.origin_m,continuation.origin_m))
    def moved(factor):
        move=lambda p:tuple(x+factor*d for x,d in zip(p,shift))
        return replace(continuation,main_start_m=move(continuation.main_start_m),
                       main_end_m=move(continuation.main_end_m),
                       lap_segments_m=tuple((move(a),move(b)) for a,b in continuation.lap_segments_m))
    assert physical_laps((initial,moved(1)))==()  # coincident axes are not two physical bars
    assert physical_laps((initial,moved(-1)))==() # separated by twice the diameter
    assert len(physical_laps(run))==1


def test_dense_repartition_rejects_contact_lane_instead_of_overlapping_neighbours():
    rules=tuple(replace(rule,enabled=rule.key=='mesh_x',spacing_cm=2.2) for rule in default_zapata_rules())
    assembly=build_footing_assembly(ZapataGeometry.from_centimetres(73.8,1159.6,150),
                                  Cover.from_centimetres(7.5,5,5),rules)
    assert not assembly.is_valid
    assert not assembly.bars
    assert any('lado a lado' in issue.message and 'separación' in issue.message for issue in assembly.schedule.issues)


def test_legacy_coincident_axis_removal_requires_review_after_physical_translation():
    geometry=ZapataGeometry.from_centimetres(750,1159.6,150)
    cover=Cover.from_centimetres(7.5,5,5)
    rules=default_zapata_rules()
    assembly=build_footing_assembly(geometry,cover,rules)
    initial,continuation=[bar for bar in assembly.bars if bar.placement_id=='mesh_x:superior:0']
    offset=tuple(a-b for a,b in zip(continuation.origin_m,initial.origin_m))
    legacy=replace(continuation,vertices_m=tuple(tuple(x-d for x,d in zip(point,offset))
                                               for point in continuation.vertices_m))
    assert legacy.signature!=continuation.signature
    old_removal=tuple(replace(rule,removed_pieces=(RemovedPiece(legacy.id,legacy.signature),))
                      if rule.key==continuation.key else rule for rule in rules)
    updated=build_footing_assembly(geometry,cover,old_removal)
    assert not updated.is_valid
    assert any('eliminado' in issue.message and 'ya no coinciden' in issue.message for issue in updated.schedule.issues)
    # No stale removal silently attaches to the now-adjacent physical piece.
    assert len(updated.reference_bars)==len(assembly.bars)
