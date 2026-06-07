#!/usr/bin/env python3

import requests
import ipaddress
import time
import json
from pathlib import Path

# ========== КОНФИГУРАЦИЯ ==========

CONFIG = {
    "api_url": "https://stat.ripe.net/data/announced-prefixes/data.json",
    "timeout": 15,                      
    "connect_timeout": 5,               # таймаут подключения
    "delay": 1.0,                       # задержка между ASN
    "max_retries": 3,                   # количество повторов при ошибке
    "retry_delay": 5,                   # начальная задержка между повторами
    "output_file": "ipset-all.txt",
    "output_json": "ipset-all.json",
    "cache_file": "asn_cache.json",
    "use_cache": True,
}

# ==================================

ASN_LIST = {
    "Scaleway": "AS12876",
    "Hetzner": "AS24940",
    "Hetzner 2": "AS213230",
    "Hetzner 3": "AS212317",
    "Akamai": "AS20940",
    "Akamai 2": "AS16625",
    "Akamai 3": "AS12222",
    "Akamai 4": "AS33905",
    "Akamai 5": "AS21342",
    "Akamai 6": "AS32787",
    "Akamai 7": "AS35994",
    "Akamai 10": "AS18209",
    "Akamai 11": "AS24319",
    "Akamai 14": "AS31108",
    "Akamai 15": "AS34164",
    "Akamai 18": "AS213120",
    "Akamai Cloud (Linode)": "AS63949",
    "DigitalOcean": "AS14061",
    "Datacamp, CDN77": "AS60068",
    "Datacamp, CDN77 2": "AS212238",
    "Contabo, Inc.": "AS51167",
    "Contabo, Inc. 2": "AS141995",
    "Contabo, Inc. 3": "AS40021",
    "OVH": "AS16276",
    "OVH 2": "AS35540",
    "Vultr (Constant)": "AS20473",
    "Cloudflare, Inc.": "AS13335",
    "Oracle Corporation": "AS31898",
    "Amazon.com, Inc.": "AS16509",
    "Amazon.com, Inc. 2": "AS14618",
    "Amazon Data Services Ireland Ltd": "AS8987",
    "G-Core": "AS199524",
    "G-Core 2": "AS202422",
    "Roblox": "AS22697",
    "Fellowship": "AS46461",
    "Fastly": "AS54113",
    "FranTech Solutions": "AS53667",
    "LogicForge": "AS208621",
    "Cogent": "AS174",
    "Melbikomas UAB": "AS8849",
    "Melbikomas UAB 2": "AS56630",
    "M247 Europe SRL": "AS9009",
    "Hurricane Electric": "AS6939",
    "GTT Communications": "AS3257",
    "Telia Carrier": "AS1299",
    "Firstcolo": "AS44066",
    "TELECOM ITALIA SPARKLE S.p.A": "AS6762",
    "Orange (FTRSI)": "AS5511",
    "Lumen": "AS3356",
    "Scalaxy": "AS58061",
    "Zenlayer": "AS21859",
}

def load_cache():
    if CONFIG["use_cache"] and Path(CONFIG["cache_file"]).exists():
        with open(CONFIG["cache_file"], "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    if CONFIG["use_cache"]:
        with open(CONFIG["cache_file"], "w") as f:
            json.dump(cache, f, indent=2)

def fetch_prefixes(asn, name, cache):
    if asn in cache:
        print(f"[cached] {name} ({asn})")
        return cache[asn]

    print(f"[+] {name} ({asn}) ...", flush=True)
    
    for attempt in range(CONFIG["max_retries"]):
        try:
            r = requests.get(
                CONFIG["api_url"],
                params={"resource": asn, "min_peers_seeing": 1},
                timeout=(CONFIG["connect_timeout"], CONFIG["timeout"])
            )
            r.raise_for_status()
            data = r.json()
            prefixes = data.get("data", {}).get("prefixes", [])
            result = [p.get("prefix") for p in prefixes if p.get("prefix")]
            cache[asn] = result
            time.sleep(CONFIG["delay"])
            return result
        except requests.exceptions.Timeout as e:
            wait = CONFIG["retry_delay"] * (2 ** attempt)
            print(f"    ⏱ Таймаут (попытка {attempt+1}/{CONFIG['max_retries']}), ждём {wait}с...")
            if attempt < CONFIG["max_retries"] - 1:
                time.sleep(wait)
            else:
                print(f"Пропускаем {name} ({asn}) из-за таймаута")
                return []
        except Exception as e:
            print(f"Ошибка: {e}")
            return []
    
    return []

def main():
    print("Загрузка префиксов из RIPE API...\n")
    
    cache = load_cache()
    v4_all = set()
    v6_all = set()
    
    for name, asn in ASN_LIST.items():
        prefixes = fetch_prefixes(asn, name, cache)
        count = 0
        for p in prefixes:
            if not p:
                continue
            try:
                net = ipaddress.ip_network(p, strict=False)
                if net.prefixlen == 0 or not net.is_global:
                    continue
                if net.version == 4:
                    v4_all.add(net)
                else:
                    v6_all.add(net)
                count += 1
            except Exception:
                continue
        print(f"    Добавлено: {count} префиксов")
    
    save_cache(cache)
    
    v4_agg = list(ipaddress.collapse_addresses(
        sorted(v4_all, key=lambda n: (int(n.network_address), n.prefixlen))
    ))
    v6_agg = list(ipaddress.collapse_addresses(
        sorted(v6_all, key=lambda n: (int(n.network_address), n.prefixlen))
    ))
    
    def sort_key(n):
        return (n.version, int(n.network_address), n.prefixlen)
    
    v4_sorted = sorted(v4_agg, key=sort_key)
    v6_sorted = sorted(v6_agg, key=sort_key)
    
    with open(CONFIG["output_file"], "w", encoding="utf-8") as f:
        for net in v4_sorted:
            f.write(str(net) + "\n")
        for net in v6_sorted:
            f.write(str(net) + "\n")
    
    metadata = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "asn_count": len(ASN_LIST),
        "ipv4_prefixes": len(v4_sorted),
        "ipv6_prefixes": len(v6_sorted),
        "total_prefixes": len(v4_sorted) + len(v6_sorted),
        "asn_list": list(ASN_LIST.keys())
    }
    with open(CONFIG["output_json"], "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*50)
    print("ГОТОВО!")
    print(f"TXT: {CONFIG['output_file']} ({len(v4_sorted)} IPv4 + {len(v6_sorted)} IPv6)")
    print(f"JSON: {CONFIG['output_json']}")
    print("="*50)

if __name__ == "__main__":
    main()
