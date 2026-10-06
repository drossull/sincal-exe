"""Load the compiled COM server without registration, Explorer, or CAD writes."""
import ctypes as c
from pathlib import Path
import sys
import uuid


class GUID(c.Structure):
    _fields_ = [('bytes', c.c_ubyte * 16)]


def guid(value):
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def method(pointer, index, *args):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(c.c_long, c.c_void_p, *args)(table[index])


def main(path):
    dll = c.WinDLL(str(Path(path).resolve()))
    ole = c.OleDLL('ole32')
    ole.CoTaskMemFree.argtypes = [c.c_void_p]
    ole.CoInitialize(None)
    try:
        dll.DllGetClassObject.argtypes = [c.POINTER(GUID), c.POINTER(GUID), c.POINTER(c.c_void_p)]
        factory_iid = guid('00000001-0000-0000-C000-000000000046')
        command_iid = guid('a08ce4d0-fa25-44ab-b57c-c7b1c323e0b9')
        assert dll.DllCanUnloadNow() == 0
        for index in range(1, 6):
            clsid = guid(f'8549E221-34D5-4E21-937C-22D8F030010{index}')
            factory, command = c.c_void_p(), c.c_void_p()
            assert dll.DllGetClassObject(c.byref(clsid), c.byref(factory_iid), c.byref(factory)) == 0
            try:
                assert method(factory, 3, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p))(
                    factory, None, c.byref(command_iid), c.byref(command)) == 0
                try:
                    title = c.c_void_p()
                    assert method(command, 3, c.c_void_p, c.POINTER(c.c_void_p))(command, None, c.byref(title)) == 0
                    print(c.wstring_at(title))
                    ole.CoTaskMemFree(title)
                    state = c.c_uint()
                    assert method(command, 7, c.c_void_p, c.c_int, c.POINTER(c.c_uint))(command, None, 0, c.byref(state)) == 0
                    assert state.value == 1  # ECS_DISABLED with no selection.
                finally:
                    method(command, 2)(command)
            finally:
                method(factory, 2)(factory)
        assert dll.DllCanUnloadNow() == 0
        print('COM factory checks passed; no registration or drawing operations.')
    finally:
        ole.CoUninitialize()


if __name__ == '__main__':
    main(sys.argv[1])
