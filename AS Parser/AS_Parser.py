#!/usr/bin/env python3
import ipaddress
import logging
import concurrent.futures as cf

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://bgp.tools/table.txt"
CHEBURCHECK_URL = "https://raw.githubusercontent.com/123jjck/cdn-ip-ranges/main/all/all_plain.txt"

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
WORKERS = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

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
session.headers.update(HEADERS)

retry = Retry(total=5,backoff_factor=1.5,status_forcelist=(429, 500, 502, 503, 504),allowed_methods=("GET",))
session.mount("https://",HTTPAdapter(max_retries=retry, pool_connections=WORKERS, pool_maxsize=WORKERS))

def load_cheburcheck() -> tuple[set, set]:
    v4 = set()
    v6 = set()
    log.info("Загрузка актуальной базы Cheburcheck...")
    try:
        r = session.get(CHEBURCHECK_URL, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        r.raise_for_status()
    except Exception as e:
        log.error("Не удалось загрузить Cheburcheck: %s", e)
        raise
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
        except ValueError:
            continue
        if net.prefixlen == 0:
            continue
        if not net.is_global:
            continue
        if net.version == 4:
            v4.add(net)
        else:
            v6.add(net)
    log.info(
        "Cheburcheck: IPv4=%d | IPv6=%d | Всего=%d",
        len(v4),
        len(v6),
        len(v4) + len(v6),
    )
    if not v4 and not v6:
        raise RuntimeError("Cheburcheck вернул пустой список")
    return v4, v6

def get_prefixes_from_bgptools() -> dict:
    prefixes_by_asn = {}
    
    log.info("Загрузка полной таблицы маршрутизации из BGP.Tools...")
    r = session.get(
        API_URL,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT * 2),
        headers={"Referer": "https://bgp.tools/"},
    )
    r.raise_for_status()
    
    for line in r.text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        
        parts = line.split()
        if len(parts) >= 2:
            prefix = parts[0]
            asn = parts[1]
            
            if not asn.startswith("AS"):
                asn = f"AS{asn}"
            
            if asn not in prefixes_by_asn:
                prefixes_by_asn[asn] = set()
            prefixes_by_asn[asn].add(prefix)
    
    log.info("BGP.Tools: загружено %d ASN", len(prefixes_by_asn))
    return prefixes_by_asn

def intersect_networks_fast(networks: set, cheburcheck: set) -> set:
    result = set()
    if not networks or not cheburcheck:
        return result

    cc_sorted = sorted(
        cheburcheck, key=lambda n: (n.version, int(n.network_address), n.prefixlen)
    )

    for net in networks:
        net_start = int(net.network_address)
        net_end = int(net.broadcast_address)
        net_version = net.version

        left, right = 0, len(cc_sorted)
        while left < right:
            mid = (left + right) // 2
            cc_net = cc_sorted[mid]
            if cc_net.version < net_version:
                left = mid + 1
            elif cc_net.version > net_version:
                right = mid
            elif int(cc_net.network_address) < net_start:
                left = mid + 1
            else:
                right = mid

        check_start = max(0, left - 20)
        check_end = min(len(cc_sorted), left + 20)

        for i in range(check_start, check_end):
            cc_net = cc_sorted[i]
            if cc_net.version != net_version:
                continue

            cc_start = int(cc_net.network_address)
            cc_end = int(cc_net.broadcast_address)

            if net_start > cc_end or cc_start > net_end:
                continue

            if cc_net.subnet_of(net):
                result.add(cc_net)
            elif net.subnet_of(cc_net):
                result.add(net)

    return result

def fetch(name: str,asn: str,cheburcheck_v4: set,cheburcheck_v6: set,bgptools_data: dict,) -> tuple[str, set, set]:
    v4 = set()
    v6 = set()
    
    all_prefixes = bgptools_data.get(asn, set())
    
    if not all_prefixes:
        log.warning("%s (%s): нет данных в BGP.Tools", name, asn)
        return name, v4, v6

    v4_networks = set()
    v6_networks = set()

    for prefix in all_prefixes:
        try:
            net = ipaddress.ip_network(prefix, strict=False)
        except ValueError:
            continue
        if net.prefixlen == 0 or not net.is_global:
            continue
        if net.version == 4:
            v4_networks.add(net)
        else:
            v6_networks.add(net)

    total_count = len(v4_networks) + len(v6_networks)
    v4 = intersect_networks_fast(v4_networks, cheburcheck_v4)
    v6 = intersect_networks_fast(v6_networks, cheburcheck_v6)
    log.info(
        "%s (%s): Всего префиксов=%d | Cheburcheck match=%d",
        name,
        asn,
        total_count,
        len(v4) + len(v6),
    )
    return name, v4, v6

def main() -> None:
    cheburcheck_v4, cheburcheck_v6 = load_cheburcheck()
    bgptools_data = get_prefixes_from_bgptools()
    
    log.info("Старт сбора для %d ASN (workers=%d)", len(ASN_LIST), WORKERS)

    results = {}
    v4_all, v6_all = set(), set()

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(
                fetch, name, asn, cheburcheck_v4, cheburcheck_v6, bgptools_data
            ): name
            for name, asn in ASN_LIST.items()
        }

        for future in cf.as_completed(futures):
            name, v4, v6 = future.result()
            results[name] = (v4, v6)
            v4_all |= v4
            v6_all |= v6

    log.info("\nРезультаты в порядке ASN_LIST:")
    for name in ASN_LIST.keys():
        if name in results:
            v4, v6 = results[name]
            log.info(
                "  %-30s: IPv4=%d, IPv6=%d, Всего=%d",
                name,
                len(v4),
                len(v6),
                len(v4) + len(v6),
            )

    v4_sorted = sorted(
        ipaddress.collapse_addresses(
            sorted(v4_all, key=lambda n: (int(n.network_address), n.prefixlen))
        ),
        key=lambda n: (int(n.network_address), n.prefixlen),
    )
    v6_sorted = sorted(
        ipaddress.collapse_addresses(
            sorted(v6_all, key=lambda n: (int(n.network_address), n.prefixlen))
        ),
        key=lambda n: (int(n.network_address), n.prefixlen),
    )

    with open("ipset-all.txt", "w", encoding="utf-8") as f:
        for net in v4_sorted:
            f.write(str(net) + "\n")
        for net in v6_sorted:
            f.write(str(net) + "\n")

    log.info(
        "Готово! IPv4: %d | IPv6: %d | Всего: %d",
        len(v4_sorted),
        len(v6_sorted),
        len(v4_sorted) + len(v6_sorted),
    )

if __name__ == "__main__":
    main()
