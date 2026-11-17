"""Write build\\version_info.txt for PyInstaller (shown in PrimeWriter.exe > Properties > Details)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from writer import APP_NAME, COPYRIGHT, __author__, __version__  # noqa: E402

nums = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{__author__}'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'PrimeWriter'),
      StringStruct('LegalCopyright', '{COPYRIGHT}. PolyForm Noncommercial 1.0.0.'),
      StringStruct('OriginalFilename', 'PrimeWriter.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
(ROOT / "build").mkdir(exist_ok=True)
(ROOT / "build" / "version_info.txt").write_text(text, encoding="utf-8")
print("version", __version__)
