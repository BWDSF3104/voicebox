"""Voicebox クローズ終了テスト(CTypes版).
usage: python vb_close_test.py --exe PATH [--keep 0|1] [--start 0|1] [--stop 0|1]
       [--wait-port-sec N] [--expect-exit 0|1] [--expect-port-open 0|1]
"""
import argparse
import ctypes
import os
import subprocess
import sys
import time

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def visible_windows_of(pid):
    found = []

    def cb(hwnd, _):
        wp = ctypes.c_uint(0)
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(wp))
        if wp.value == pid and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def port_open(port):
    import socket
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def voicebox_procs():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    names = [l.split(",")[0].strip('"') for l in out.splitlines() if "voicebox" in l.lower()]
    return names


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--exe", required=True)
    p.add_argument("--keep", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--stop", default=None)
    p.add_argument("--wait-port-sec", type=int, default=0)
    p.add_argument("--init-wait", type=int, default=10)
    p.add_argument("--expect-exit", type=int, required=True)
    p.add_argument("--expect-port-open", type=int, default=0)
    a = p.parse_args()

    env = os.environ.copy()
    for k, v in (("VB_TEST_KEEP", a.keep), ("VB_TEST_START", a.start), ("VB_TEST_STOP", a.stop)):
        env.pop(k, None)
        if v is not None:
            env[k] = v

    proc = subprocess.Popen([a.exe], cwd=os.path.dirname(a.exe), env=env)
    print(f"[start] pid={proc.pid}", flush=True)

    if a.wait_port_sec:
        end = time.time() + a.wait_port_sec
        while time.time() < end and not port_open(17493):
            time.sleep(2)
        print(f"[server] port17493open={port_open(17493)}", flush=True)
    else:
        time.sleep(a.init_wait)

    print(f"[step] wait done, alive={proc.poll() is None}", flush=True)
    hwnds = []
    deadline = time.time() + 60
    while time.time() < deadline:
        hwnds = visible_windows_of(proc.pid)
        if hwnds:
            break
        time.sleep(2)
    print(f"[step] windows={len(hwnds)}", flush=True)
    if not hwnds:
        # 診断: 全可視ウィンドウとそのpid
        all_w = []

        def diag(h, _):
            wp = ctypes.c_uint(0)
            user32.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(wp))
            if user32.IsWindowVisible(ctypes.c_void_p(h)):
                all_w.append((h, wp.value))
            return True
        user32.EnumWindows(EnumWindowsProc(diag), 0)
        print(f"[diag] visible windows with pids: {all_w[:20]}", flush=True)
        proc.kill()
        subprocess.run("taskkill /F /T /IM voicebox-server-cuda.exe", shell=True, capture_output=True)
        subprocess.run("taskkill /F /T /IM voicebox-server-x86_64-pc-windows-msvc.exe", shell=True, capture_output=True)
        print("RESULT=FAIL (no window)", flush=True)
        return 1
    res = ctypes.c_size_t(0)
    user32.SendMessageTimeoutW(ctypes.c_void_p(hwnds[0]), 0x0010, 0, 0, 0x0002, 3000, ctypes.byref(res))
    print("[close] WM_CLOSE sent", flush=True)

    end = time.time() + 30
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
    time.sleep(8)

    main_alive = proc.poll() is None
    popen = port_open(17493)
    procs = voicebox_procs()
    print(f"[after] mainAlive={main_alive} port17493open={popen} procs={procs}", flush=True)

    ok = (main_alive != bool(a.expect_exit)) and (popen == bool(a.expect_port_open)) and ((not a.expect_exit) or not procs)
    print(f"RESULT={'PASS' if ok else 'FAIL'} (expect: exit={a.expect_exit} portOpen={a.expect_port_open})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
