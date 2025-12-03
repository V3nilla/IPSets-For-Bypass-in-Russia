#!/usr/bin/env python3
import requests
import ipaddress
import time

ASN_LIST = {
    "Scaleway": "AS12876",
    "Hetzner": "AS24940",
    "Akamai": "AS20940",
    "DigitalOcean": "AS14061",
    "Datacamp": "AS60068",
    "Contabo": "AS51167",
    "OVH": "AS16276",
    "Constant": "AS20473",
    "Cloudflare": "AS13335",
    "Oracle": "AS31898",
    "Amazon": "AS16509",
    "G-Core": "AS199524",
    "Roblox": "AS22697",
}

API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"
TIMEOUT = 15  # секунд

v4_all = set()
v6_all = set()

for name, asn in ASN_LIST.items():
    print(f"[+] Обработка {name} ({asn}) ...", flush=True)
    try:
        r = requests.get(API_URL, params={"resource": asn, "min_peers_seeing": 1}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json().get("data", {}).get("prefixes", [])
        count = 0
        for p in data:
            prefix = p.get("prefix")
            if not prefix:
                continue
            try:
                net = ipaddress.ip_network(prefix, strict=False)
                if net.version == 4:
                    v4_all.add(net)
                else:
                    v6_all.add(net)
                count += 1
            except Exception:
                continue
        print(f"    {count} префиксов добавлено")
    except Exception as e:
        print(f"    Ошибка при получении {asn}: {e}")
    time.sleep(1.0)  # чтобы не бомбить API

v4_agg = list(ipaddress.collapse_addresses(sorted(v4_all, key=lambda n: (int(n.network_address), n.prefixlen))))
v6_agg = list(ipaddress.collapse_addresses(sorted(v6_all, key=lambda n: (int(n.network_address), n.prefixlen))))

def sort_key(n):
    return (n.version, int(n.network_address), n.prefixlen)

v4_sorted = sorted(v4_agg, key=sort_key)
v6_sorted = sorted(v6_agg, key=sort_key)

with open("all_prefixes_aggregated.txt", "w", encoding="utf-8") as f:
    for net in v4_sorted:
        f.write(str(net) + "\n")
    for net in v6_sorted:
        f.write(str(net) + "\n")

print("\nГотово!")
print(f"IPv4: {len(v4_sorted)} | IPv6: {len(v6_sorted)} | Всего: {len(v4_sorted)+len(v6_sorted)}")
print("Файл сохранён как all_prefixes_aggregated.txt")


