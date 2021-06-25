# NetworkPingComparator

NetworkPingComparator is a Python module for pinging two networks and displaying the difference in host reponses.

## Usage

```python
from network_ping_comparator import NetworkPingComparator

# define networks to test
NETWORK_1 = "192.168.1.0/24"
NETWORK_2 = "192.168.2.0/24"

# list of excluded addresses
EXCLUDED_IP = ["0", "255"]

comparator = NetworkPingComparator(NETWORK_1, NETWORK_2)
comparator.exclude_ip(EXCLUDED_IP)
comparator.run()
result = comparator.output()
if result:
    print(f"Address(es) failed to match ping responses: {result}")
else:
    print("Complete, no address response mismatch detected")
```

## License
[None]
