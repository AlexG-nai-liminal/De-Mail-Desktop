"""Small Windows DPAPI adapter with no persistent plaintext secret."""

import ctypes
import sys
from ctypes import wintypes


class CredentialProtectionError(OSError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


class DpapiProtector:
    _UI_FORBIDDEN = 0x1

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Windows DPAPI is available only on Windows.")

    def protect(self, plaintext: bytes) -> bytes:
        source, source_buffer = self._blob(plaintext)
        output = _DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        function = crypt32.CryptProtectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DataBlob),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        function.restype = wintypes.BOOL
        result = function(
            ctypes.byref(source),
            "de-Mail Desktop credentials",
            None,
            None,
            None,
            self._UI_FORBIDDEN,
            ctypes.byref(output),
        )
        del source_buffer
        return self._take_output(result, output, "CryptProtectData")

    def unprotect(self, ciphertext: bytes) -> bytes:
        source, source_buffer = self._blob(ciphertext)
        output = _DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        function = crypt32.CryptUnprotectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(_DataBlob),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        function.restype = wintypes.BOOL
        result = function(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            self._UI_FORBIDDEN,
            ctypes.byref(output),
        )
        del source_buffer
        return self._take_output(result, output, "CryptUnprotectData")

    @staticmethod
    def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        source_buffer = ctypes.create_string_buffer(value)
        source = _DataBlob(
            len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte))
        )
        return source, source_buffer

    @staticmethod
    def _take_output(result: int, output: _DataBlob, function_name: str) -> bytes:
        if not result:
            raise CredentialProtectionError(ctypes.get_last_error(), f"{function_name} failed")
        try:
            return ctypes.string_at(output.data, output.size)
        finally:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
            kernel32.LocalFree.restype = wintypes.HLOCAL
            kernel32.LocalFree(output.data)
