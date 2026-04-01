import urllib.request
import os

URL = "https://github.com/Badlakes/zenonzard_rebirth/releases/download/latest/ocgcore.dll"

print("Baixando ocgcore.dll...")
urllib.request.urlretrieve(URL, "ocgcore.dll")
print("OK")
