"""
This module pings two networks and identifies ip addresses that respond on one network but not on the other
"""

import ipaddress
from multiprocessing import Process, Manager
import platform
from subprocess import Popen, DEVNULL, STDOUT
from typing import List

# define networks to test
NETWORK_1 = "192.168.1.0/24"
NETWORK_2 = "192.168.2.0/24"

# list of excluded addresses
EXCLUDED_HOST = ["0", "255"]


class NetworkPingComparator:
    """
    A class to perform the network ping comparison
    """

    # ping parameters
    NUM_PACKETS = 1  # num of packets to send in ping
    NUM_ATTEMPTS = 2  # num of attempts to reach host
    TIMEOUT = 2  # ping timeout time in seconds

    def __init__(self, network_1: str, network_2: str):
        """
        NetworkPingComparator constructor

        :param network_1: string representing a IPv4 network
        :param network_2: string representing a IPv4 network
        """
        self.networks = [network_1, network_2]
        self.excluded_host = None
        self.hosts = None
        self.ping_failures = None

    def run(self) -> None:
        """
        Run the ping commands for both networks in separate processes

        :return: None
        """
        self.ping_failures = Manager().dict()  # Manager dict used to share type between separate processes
        p = {}
        for network in self.networks:
            # start a process for each network
            p[network] = Process(target=self.not_pingable, args=(network, self.ping_failures))
            p[network].start()
            print(f"Pinging network {network}")
        for network in self.networks:
            # wait for each process to complete
            p[network].join()

    def output(self) -> List[str]:
        """
        Returns a list of IP addresses that didn't respond to a ping on their subnet but did on the other subnet

        :return: List of strings for each address that didn't respond
        """
        if self.ping_failures is not None:  # if ping_failures is None, then run() hasn't ran yet
            subnet = {}
            octet = {}

            for network in self.networks:
                # format subnet and octet strings
                subnet[network] = network.rsplit('.', 1)[0]
                octet[network] = [str(ip).split('.')[3] for ip in self.ping_failures[network]]

            # determine which IP addresses are not responding on one network but they are on the other
            not_pingable_on_net1 = list(set(octet[self.networks[0]]).difference(octet[self.networks[1]]))
            not_pingable_on_net2 = list(set(octet[self.networks[1]]).difference(octet[self.networks[0]]))

            # return with a list of the full IP addresses for the non-responsive hosts
            return [f"{subnet[self.networks[0]]}.{ip}" for ip in not_pingable_on_net1] + \
                   [f"{subnet[self.networks[1]]}.{ip}" for ip in not_pingable_on_net2]

        else:  # run the processes to get data then output the data
            self.run()
            self.output()

    def exclude_host(self, excluded_host: List[str]) -> None:
        """
        Use to exclude one or more host IP addresses

        :param excluded_host: List of strings representing last octet of IPv4 address for excluded hosts
        :return: None
        """
        self.excluded_host = excluded_host

    def not_pingable(self, network, ping_failures) -> None:
        """
        Adds list of unresponsive hosts to dictionary under network name

        :param network: String of network IPv4 address
        :param ping_failures: Manager.dict representing unresponsive hosts for each network
        :return: None
        """
        self.hosts = list(ipaddress.ip_network(network).hosts())

        # ping network
        failures = self.__ping_network()

        # loop for number of re-attempts to reach host
        for _ in range(self.NUM_ATTEMPTS-1):
            # if there are failures try again
            if not failures:
                break
            else:
                self.hosts = failures
                failures = self.__ping_network()

        ping_failures[network] = failures

    def __ping_network(self) -> List[str]:
        """
        Ping all hosts in network and collect exit_codes

        :return: List of ip addresses that failed to respond to ping
        """
        procs = self.__spawn_ping_procs()

        # wait for subprocesses to complete and get exit codes
        exit_codes = {ip: procs[ip].wait() for ip in procs}

        # ping response failure occurs when exit code from subprocess is not 0
        # put ip address of host and exit code into failure dictionary
        failures = {ip: exit_code for ip, exit_code in exit_codes.items() if exit_code != 0}

        return list(failures.keys())

    def __spawn_ping_procs(self) -> dict:
        """
        Spawn subprocesses for ping commands to hosts, except for any excluded hosts

        :return: dict of processes for each host
        """
        procs = {}
        for host in self.hosts:
            if self.excluded_host:
                if str(host).split('.')[3] in self.excluded_host:
                    continue
            procs[host] = self.ping(host)
        return procs

    def ping(self, host) -> Popen:
        """
        Send ping command to host using subprocess

        :param host: IP address for host
        :return: subprocess
        """
        if platform.system().lower() == "windows":
            ping_args = ['-n', '-w', self.TIMEOUT*1000]
        else:
            ping_args = ['-c', '-W', self.TIMEOUT]
        return Popen(['ping', ping_args[0], str(self.NUM_PACKETS), str(host), ping_args[1], str(ping_args[2])],
                     stdout=DEVNULL, stderr=STDOUT)


if __name__ == '__main__':  # pragma: no cover
    comparator = NetworkPingComparator(NETWORK_1, NETWORK_2)
    comparator.exclude_host(EXCLUDED_HOST)
    comparator.run()
    result = comparator.output()
    if result:
        print(f"Address(es) failed to match ping responses: {result}")
    else:
        print("Complete, no address response mismatch detected")
