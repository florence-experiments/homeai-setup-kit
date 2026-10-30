"""Small Windows helpers (ctypes + built-in tools). On other systems they degrade to no-ops
so the rest of the watcher can be tested anywhere."""
import ctypes
import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0


def run(args, timeout=15):
    """Run a built-in tool without flashing a console window. Returns (returncode, bytes)."""
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e).encode()


def is_admin():
    if not IS_WIN:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ----------------------------------------------------------------------------- processes
if IS_WIN:
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    _k32.QueryDosDeviceW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    INVALID_HANDLE = wintypes.HANDLE(-1).value


def list_processes():
    """{pid: (ppid, exe_name)} using a Toolhelp snapshot (cheap, no child process)."""
    if not IS_WIN:
        return {}
    snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == INVALID_HANDLE:
        return {}
    out = {}
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = _k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile)
            ok = _k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k32.CloseHandle(snap)
    return out


def process_image(pid):
    """Full path of a running process, or '' if it is gone / not accessible."""
    if not IS_WIN:
        return ""
    h = _k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        _k32.CloseHandle(h)


def descendants(pid, procs):
    """All descendants of pid (children first, deepest first) from a list_processes() map."""
    children = {}
    for p, (pp, _) in procs.items():
        children.setdefault(pp, []).append(p)
    order, stack, seen = [], [pid], set()
    while stack:
        cur = stack.pop()
        for c in children.get(cur, []):
            if c not in seen and c != cur:
                seen.add(c)
                order.append(c)
                stack.append(c)
    return list(reversed(order))


def kill_pid(pid):
    if not IS_WIN:
        return False, "not on Windows"
    rc, out = run(["taskkill", "/F", "/PID", str(int(pid))], timeout=10)
    return rc == 0, out.decode(errors="replace").strip()


def memory_mb():
    if not IS_WIN:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            return None

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    try:
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024.0 * 1024.0)
    except Exception:
        pass
    return None


_DEVMAP = None


def device_to_dos(path):
    r"""5157 events give '\device\harddiskvolume3\users\...'; turn it into 'C:\users\...'."""
    global _DEVMAP
    if not path or not path.lower().startswith("\\device\\") or not IS_WIN:
        return path
    if _DEVMAP is None:
        _DEVMAP = {}
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            buf = ctypes.create_unicode_buffer(512)
            if _k32.QueryDosDeviceW(letter + ":", buf, 512):
                _DEVMAP[buf.value.lower()] = letter + ":"
    low = path.lower()
    for dev, drive in _DEVMAP.items():
        if low.startswith(dev + "\\"):
            return drive + path[len(dev):]
    return path


def service_running(name):
    if not IS_WIN:
        return None
    rc, out = run(["sc", "query", name], timeout=5)
    return b"RUNNING" in out


def message_box(title, text):
    """Fallback alert when tkinter is unavailable (blocking, so call it from a thread)."""
    if IS_WIN:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x00041030)  # topmost | warning | setforeground


def kill_many(pids):
    """Close each pid in order; returns [(pid, ok, message)]."""
    return [(p,) + tuple(kill_pid(p)) for p in pids]
