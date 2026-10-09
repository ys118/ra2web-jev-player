import os
import shutil
import subprocess
import time


def _agent_browser():
    """agent-browser CLI path: env AGENT_BROWSER_CMD wins, else PATH."""
    env = os.environ.get("AGENT_BROWSER_CMD")
    if env:
        return env
    for name in ("agent-browser", "agent-browser.cmd", "agent-browser.exe"):
        found = shutil.which(name)
        if found:
            return found
    return "agent-browser"


AB = [_agent_browser(), "--session", os.environ.get("RA2WEB_SESSION", "gonghui")]
print("probe start", flush=True)
t0 = time.time()
p = subprocess.Popen(AB + ["eval", "1+1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    out, err = p.communicate(timeout=20)
    print("probe ok %.1fs out=%r" % (time.time()-t0, out[:50]), flush=True)
except subprocess.TimeoutExpired:
    print("probe TIMEOUT after %.1fs" % (time.time()-t0), flush=True)
    subprocess.run(["taskkill","/PID",str(p.pid),"/T","/F"], capture_output=True)
