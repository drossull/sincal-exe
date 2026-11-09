from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_cleanup_never_zooms_or_changes_viewports():
    # Cleanup may run with an unlocked floating viewport active. A ZOOM here
    # silently changes the printed scale/centre before QSAVE.
    for name in ('scripts/PURGEALL.ps1', 'scripts/PURGEALL.scr', 'lisps/PURGEALL.lsp', 'lisps/VG.lsp'):
        source = (ROOT / name).read_text(encoding='utf-8')
        assert not re.search(r'(?i)\b(?:ZOOM|MSPACE|PSPACE|VPORTS)\b', source), name


def test_side_database_saves_check_viewports():
    source=(ROOT/'src/Sincal.DwgProps/Commands.cs').read_text(encoding='utf-8')
    saves = list(re.finditer(r'\bdatabase\.SaveAs\(([^;]+)\);', source))
    assert saves
    for index, save in enumerate(saves):
        assert re.sub(r'\s+', '', save.group(1)) == (
            'request.saved,true,database.OriginalFileVersion,database.SecurityParameters')
        end = saves[index + 1].start() if index + 1 < len(saves) else len(source)
        verification = re.sub(r'\s+', '', source[save.end():end])
        assert '.ReadDwgFile(request.saved,' in verification
        assert re.search(r'ViewportIntegrity\.Verify\(\w+,viewports\)', verification)
