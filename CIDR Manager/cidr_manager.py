import ipaddress
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def main():
    input_file = "ipset-cloudflare.txt"
    output_file = "cleaned_and_aggregated_ipset-cloudflare.txt"

    with open(input_file) as file:
        raw_lines = [line.strip() for line in file if line.strip()]
    
    logging.info(f"Loaded {len(raw_lines)} entries from {input_file}")

    subnets = []
    seen = set()
    for line in raw_lines:
        try:
            net = ipaddress.IPv4Network(line, strict=False)
            if net in seen:
                logging.warning(f"Duplicate found and skipped: {net}")
            else:
                seen.add(net)
                subnets.append(net)
        except ValueError as e:
            logging.error(f"Invalid subnet '{line}': {e}")

    aggregated = list(ipaddress.collapse_addresses(subnets))
    aggregated.sort(key=lambda net: int(net.network_address))

    with open(output_file, "w") as out_file:
        for net in aggregated:
            out_file.write(str(net) + "\n")

    logging.info(f"Aggregated list written to {output_file} ({len(aggregated)} entries)")

if __name__ == "__main__":
    main()
