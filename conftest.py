# conftest.py - pytest 設定檔
# 防止 web_app.py 裡的 sys.stdout = io.TextIOWrapper(...) 破壞 pytest capture 機制

import sys
import io

# pytest 執行環境下，sys.stdout 是 _pytest.capture.EncodedFile
# 它有 .buffer 屬性但不支援 io.TextIOWrapper 的 seek 操作
# 所以在這裡把 sys.stdout 的 buffer 屬性暫時移除，讓 web_app.py 的守衛跳過替換

_orig_stdout = sys.stdout

class _SafeStdout:
    """包裝 pytest 的 stdout，隱藏 .buffer 避免 TextIOWrapper 替換"""
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __getattr__(self, name):
        if name == 'buffer':
            raise AttributeError('buffer hidden by conftest')
        return getattr(self._wrapped, name)

    def write(self, s):
        return self._wrapped.write(s)

    def flush(self):
        return self._wrapped.flush()


def pytest_configure(config):
    """在所有 import 前替換 stdout，讓 web_app.py 無法 wrap"""
    sys.stdout = _SafeStdout(sys.stdout)


def pytest_unconfigure(config):
    """測試結束後還原"""
    if isinstance(sys.stdout, _SafeStdout):
        sys.stdout = sys.stdout._wrapped
