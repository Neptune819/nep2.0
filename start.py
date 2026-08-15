"""NEP 启动脚本 - 自动检查依赖、启动服务器、打开浏览器"""
import subprocess
import sys
import os
import time
import socket
import webbrowser

PORT = 5000
URL = f"http://127.0.0.1:{PORT}"
TIMEOUT = 30

def find_python():
    """返回当前 Python 解释器路径"""
    return sys.executable

def check_deps():
    """检查核心依赖是否已安装"""
    try:
        import flask
        import sklearn
        return True
    except ImportError:
        return False

def install_deps(python):
    """安装依赖"""
    pkgs = "flask requests python-dotenv scikit-learn numpy jieba Pillow python-docx pypdf"
    mirrors = [
        ("http://mirrors.aliyun.com/pypi/simple/", "mirrors.aliyun.com"),
        ("https://pypi.tuna.tsinghua.edu.cn/simple/", "pypi.tuna.tsinghua.edu.cn"),
        (None, None),  # default
    ]
    for index, host in mirrors:
        label = host or "pypi.org"
        print(f"  Installing from {label}...")
        cmd = [python, "-m", "pip", "install"] + pkgs.split() + [
            "-q", "--disable-pip-version-check"
        ]
        if index:
            cmd += ["-i", index, "--trusted-host", host]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0:
            return True
    return False

def kill_port(port):
    """杀掉占用指定端口的进程"""
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(["taskkill", "/f", "/pid", pid],
                                   capture_output=True)
        except Exception:
            pass

def wait_port(port, timeout):
    """等待端口就绪，返回 True/False"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print()
    print("=" * 50)
    print("  NEP Anime Recommendation System")
    print("=" * 50)
    print()

    # 1. Python
    python = find_python()
    print(f"[1/3] Python: {python}")

    # 2. Dependencies
    print("[2/3] Checking dependencies...")
    if check_deps():
        print("  Ready")
    else:
        print("  Installing (first time may take a few minutes)...")
        if not install_deps(python):
            print("\n[!] Failed to install dependencies.")
            print(f"    Please run: {python} -m pip install -r requirements.txt")
            input("Press Enter to exit...")
            return
        print("  Done")

    # 3. Kill old process
    kill_port(PORT)

    # 4. Start server
    print("[3/3] Starting server...")
    server = subprocess.Popen(
        [python, "app.py"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # 5. Wait for port
    print(f"\n  Waiting for port {PORT}...", end="", flush=True)
    if wait_port(PORT, TIMEOUT):
        print(" Ready!")
    else:
        print(f"\n\n[!] Timeout ({TIMEOUT}s). Server may have failed to start.")
        print("    Check error.log for details.")
        server.terminate()
        input("Press Enter to exit...")
        return

    # 6. Open browser
    print(f"\n  Opening browser...")
    webbrowser.open(URL)

    print()
    print("=" * 50)
    print(f"  Server running at {URL}")
    print()
    print(f"  Home:    {URL}")
    print(f"  Quiz:    {URL}/quiz")
    print(f"  MyList:  {URL}/mylist")
    print()
    print("  Close: double-click stop.bat")
    print("  Server runs in background. This window can be closed.")
    print("=" * 50)
    print()
    input("Press Enter to close this window...")

if __name__ == "__main__":
    main()
