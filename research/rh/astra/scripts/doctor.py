#!/usr/bin/env python3
import json,platform,shutil,subprocess,sys
def ver(cmd):
    try: return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=15).splitlines()[0]
    except Exception: return None
print(json.dumps({"python":sys.version.split()[0],"platform":platform.platform(),"git":ver(["git","--version"]),"lean":ver(["lean","--version"]) if shutil.which("lean") else None,"lake":ver(["lake","--version"]) if shutil.which("lake") else None,"coqc":ver(["coqc","--version"]) if shutil.which("coqc") else None,"rh_status":"NOT_PROVEN","authority_effect":"NONE"},sort_keys=True,indent=2))
