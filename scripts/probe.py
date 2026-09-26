import subprocess, time, base64, sys
AB = ["C:/Program Files/nodejs/agent-browser.cmd", "--session", "gonghui"]
print("probe start", flush=True)
t0 = time.time()
p = subprocess.Popen(AB + ["eval", "1+1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    out, err = p.communicate(timeout=20)
    print("probe ok %.1fs out=%r" % (time.time()-t0, out[:50]), flush=True)
except subprocess.TimeoutExpired:
    print("probe TIMEOUT after %.1fs" % (time.time()-t0), flush=True)
    subprocess.run(["taskkill","/PID",str(p.pid),"/T","/F"], capture_output=True)
