#!/usr/bin/env python3
import ipaddress
import logging
import concurrent.futures as cf

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
WORKERS = 6  # число параллельных запросов

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Имя провайдера/сети -> ASN
ASN_LIST = {
    "Scaleway": "AS12876",
    "Hetzner": "AS24940",
    "Hetzner 2": "AS213230",
    "Hetzner 3": "AS212317",
    "Hetzner 4": "AS215859",
    "Akamai": "AS20940",
    "Akamai 2": "AS16625",
    "Akamai 3": "AS12222",
    "Akamai 4": "AS33905",
    "Akamai 5": "AS21342",
    "Akamai 6": "AS32787",
    "Akamai 7": "AS35994",
    "Akamai 8": "AS12400",
    "Akamai 9": "AS15802",
    "Akamai 10": "AS18209",
    "Akamai 11": "AS24319",
    "Akamai 12": "AS25019",
    "Akamai 13": "AS26008",
    "Akamai 14": "AS31108",
    "Akamai 15": "AS34164",
    "Akamai 16": "AS49846",
    "Akamai 17": "AS17204",
    "Akamai 18": "AS213120",
    "Akamai 19": "AS393234",
    "Akamai 20": "AS393560",
    "Akamai Cloud (Linode)": "AS63949",
    "DigitalOcean": "AS14061",
    "DigitalOcean 2": "AS46652",
    "DigitalOcean 3": "AS393406",
    "Datacamp, CDN77": "AS60068",
    "Datacamp, CDN77 2": "AS212238",
    "Contabo": "AS51167",
    "Contabo 2": "AS141995",
    "Contabo 3": "AS40021",
    "OVH": "AS16276",
    "OVH 2": "AS35540",
    "Vultr (Constant)": "AS20473",
    "Cloudflare": "AS13335",
    "Cloudflare 2": "AS14789",
    "Cloudflare 3": "AS132892",
    "Cloudflare 4": "AS395747",
    "Cloudflare 5": "AS209242",
    "Clouvider": "AS62240",
    "CreaNova": "AS51765",
    "Oracle Cloud": "AS31898",
    "Oracle 2": "AS1219",
    "Amazon": "AS16509",
    "Amazon 2": "AS14618",
    "Amazon 3": "AS8987",
    "G-Core": "AS199524",
    "G-Core 2": "AS202422",
    "Fellowship": "AS46461",
    "Fastly": "AS54113",
    "FranTech": "AS53667",
    "LogicForge": "AS208621",
    "Hostinger": "AS47583",
    "Hostinger 2": "AS204915",
    "Ionos": "AS8560",
    "Ionos 2": "AS15418",
    "DreamHost": "AS29873",
    "GoDaddy": "AS26496",
    "GoDaddy 2": "AS398101",
    "HostGator, BlueHost": "AS46606",
    "Cogent": "AS174",
    "Riot Games, Inc": "AS6507",
    "I3DNET (Discord)": "AS49544",
    "IOMART": "AS20860",
    "IOMART 2": "AS21130",
    "Google Cloud": "AS15169",
    "Microsoft Azure": "AS8075",
    "Melbicom": "AS8849",
    "Melbicom 2": "AS56630",
    "M247 Europe SRL": "AS9009",
    "M247 Europe SRL 2": "AS39675",
    "HostPapa, ColoCrossing": "AS36352",
    "Hurricane Electric": "AS6939",
    "GTT Communications": "AS3257",
    "NTT Global": "AS2914",
    "Telia Carrier": "AS1299",
    "Firstcolo": "AS44066",
    "Hosteur": "AS20773",
    "ITL DC": "AS210403",
    "TELECOM ITALIA SPARKLE S.p.A": "AS6762",
    "Orange (FTRSI)": "AS5511",
    "GlobeNet": "AS52320",
    "Lumen": "AS3356",
    "Tata Communications": "AS6453",
    "Verizon Business": "AS701",
    "Scalaxy": "AS58061",
    "Zenlayer": "AS21859",
    "BunnyCDN": "AS5065",
    "Edgio": "AS15133",
    "Edgio 2": "AS22843",
    "StackPath": "AS33438",
    "StackPath 2": "AS202384",
    "KeyCDN": "AS199653",
    "CacheFly": "AS30081",
    "Imperva_Incapsula": "AS19551",
}

session = requests.Session()
retry = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
session.mount("https://", HTTPAdapter(max_retries=retry))


def fetch(name: str, asn: str) -> tuple[set, set]:
    v4, v6 = set(), set()

    try:
        r = session.get(
            API_URL,
            params={"resource": asn, "min_peers_seeing": 1},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        r.raise_for_status()
        prefixes = r.json().get("data", {}).get("prefixes", [])
    except Exception as e:
        log.warning("%s (%s): ошибка — %s", name, asn, e)
        return v4, v6

    for p in prefixes:
        prefix = p.get("prefix")
        if not prefix:
            continue
        try:
            net = ipaddress.ip_network(prefix, strict=False)
        except ValueError:
            continue
        if net.prefixlen == 0 or not net.is_global:
            continue
        (v4 if net.version == 4 else v6).add(net)

    log.info("%s (%s): %d префиксов", name, asn, len(v4) + len(v6))
    return v4, v6


def main() -> None:
    log.info("Старт сбора для %d ASN (workers=%d)", len(ASN_LIST), WORKERS)
    v4_all, v6_all = set(), set()

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch, name, asn) for name, asn in ASN_LIST.items()]
        for future in cf.as_completed(futures):
            v4, v6 = future.result()
            v4_all |= v4
            v6_all |= v6

    v4_sorted = sorted(
        ipaddress.collapse_addresses(sorted(v4_all, key=lambda n: (int(n.network_address), n.prefixlen))),
        key=lambda n: (int(n.network_address), n.prefixlen),
    )
    v6_sorted = sorted(
        ipaddress.collapse_addresses(sorted(v6_all, key=lambda n: (int(n.network_address), n.prefixlen))),
        key=lambda n: (int(n.network_address), n.prefixlen),
    )

    with open("ipset-all.txt", "w", encoding="utf-8") as f:
        for net in v4_sorted:
            f.write(str(net) + "\n")
        for net in v6_sorted:
            f.write(str(net) + "\n")

    log.info(
        "Готово! IPv4: %d | IPv6: %d | Всего: %d",
        len(v4_sorted), len(v6_sorted), len(v4_sorted) + len(v6_sorted),
    )


if __name__ == "__main__":
    main()
