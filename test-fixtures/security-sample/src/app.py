import subprocess


def ping(host: str) -> str:
    return subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
