"""
Unit tests for NetworkPingComparator
"""

import ipaddress
from multiprocessing import Process
from multiprocessing.managers import BaseProxy
import pytest
from subprocess import Popen

from network_ping_comparator import NetworkPingComparator, NETWORK_1, NETWORK_2

LOOP_BACK_ADDRESS = "127.0.0.1"
EXCLUDED_HOST = "1"


@pytest.fixture
def comparator():
    """ Returns a NetworkPingComparator initialized with two different networks """
    return NetworkPingComparator(NETWORK_1, NETWORK_2)


@pytest.fixture
def hosts():
    """ Returns a list of host IP addresses """
    return list(ipaddress.ip_network(NETWORK_1).hosts())


@pytest.fixture
def procs(hosts):
    """ Returns a dict of Popen processes for each IP in network """
    return {ip: Popen for ip in hosts}


def test_ctor(comparator):
    """ Test object constructor """
    assert isinstance(comparator, NetworkPingComparator)


def test_ctor_networks(comparator):
    """ Test that constructor assigns networks to list """
    assert comparator.networks == [NETWORK_1, NETWORK_2]


def test_ping_windows_platform(mocker, comparator):
    """ Test that subprocess command is correct for windows """
    mocker.patch('platform.system', return_value='Windows')
    process = comparator.ping(LOOP_BACK_ADDRESS)
    assert process.args == ['ping', '-n',  str(comparator.NUM_PACKETS), str(LOOP_BACK_ADDRESS), '-w',
                            str(comparator.TIMEOUT*1000)]


def test_ping_linux_platform(mocker, comparator):
    """ Test that subprocess command is correct for linux """
    mocker.patch('platform.system', return_value='Linux')
    process = comparator.ping(LOOP_BACK_ADDRESS)
    assert process.args == ['ping', '-c',  str(comparator.NUM_PACKETS), str(LOOP_BACK_ADDRESS), '-W',
                            str(comparator.TIMEOUT)]


def test_exlude_host(comparator):
    comparator.exclude_host(LOOP_BACK_ADDRESS)
    assert comparator.excluded_host == LOOP_BACK_ADDRESS


def test_ping_pass(mocker, comparator):
    """ Test ping returning a successful ping response (exit code = 0) """
    mocker.patch.object(NetworkPingComparator, 'ping')
    NetworkPingComparator.ping.return_value.wait.return_value = 0
    process = comparator.ping(LOOP_BACK_ADDRESS)
    assert process.wait() == 0


def test_fail(mocker, comparator):
    """ Test ping returning a failed ping response (exit code != 0) """
    mocker.patch.object(NetworkPingComparator, 'ping')
    NetworkPingComparator.ping.return_value.wait.return_value = 1
    process = comparator.ping(LOOP_BACK_ADDRESS)
    assert process.wait() == 1


def test_spawn_ping_procs(comparator, hosts):
    """ Test spawning subprocesses for each IP address ping command """
    comparator.hosts = hosts
    procs = comparator._NetworkPingComparator__spawn_ping_procs()
    assert all(isinstance(procs[ip], Popen) for ip in procs.keys())


def test_spawn_ping_procs_excluded(comparator, hosts):
    """ Test spawning subprocesses for each IP address ping command excluding specified host"""
    comparator.hosts = [str(host) for host in hosts]
    comparator.exclude_host([EXCLUDED_HOST])
    expected_hosts = [str(host) for host in hosts]
    expected_hosts.remove(NETWORK_1.split('0/')[0] + EXCLUDED_HOST)
    procs = comparator._NetworkPingComparator__spawn_ping_procs()
    assert all(isinstance(procs[ip], Popen) for ip in expected_hosts)


def test_ping_network_pass(mocker, comparator, hosts, procs):
    """ Test collecting ping pass exit codes from subprocesses for all hosts on network """
    mocker.patch.object(NetworkPingComparator, '_NetworkPingComparator__spawn_ping_procs')
    NetworkPingComparator._NetworkPingComparator__spawn_ping_procs.return_value = procs
    mocker.patch('subprocess.Popen.wait', return_value=0)
    failures = comparator._NetworkPingComparator__ping_network()
    assert failures == []


def test_ping_network_fail(mocker, comparator, hosts, procs):
    """ Test collecting ping fail exit codes from subprocesses for all hosts on network """
    mocker.patch.object(NetworkPingComparator, '_NetworkPingComparator__spawn_ping_procs')
    NetworkPingComparator._NetworkPingComparator__spawn_ping_procs.return_value = procs
    mocker.patch('subprocess.Popen.wait', return_value=1)
    failures = comparator._NetworkPingComparator__ping_network()
    assert failures == [ip for ip in hosts]


def test_not_pingable_pass(mocker, comparator, hosts):
    """ Test retry logic for ping attempts (passing) """
    mocker.patch.object(NetworkPingComparator, '_NetworkPingComparator__ping_network')
    NetworkPingComparator._NetworkPingComparator__ping_network.return_value = []
    failures = {}
    comparator.not_pingable(NETWORK_1, ping_failures=failures)
    assert failures == {}


def test_not_pingable_all_fail(mocker, comparator, hosts):
    """ Test retry logic for ping attempts (failing) """
    mocker.patch.object(NetworkPingComparator, '_NetworkPingComparator__ping_network')
    NetworkPingComparator._NetworkPingComparator__ping_network.return_value = [ip for ip in hosts]
    failures = {}
    comparator.not_pingable(NETWORK_1, ping_failures=failures)
    assert failures == {NETWORK_1: NetworkPingComparator._NetworkPingComparator__ping_network.return_value}


def test_not_pingable_one_fail(mocker, comparator, hosts):
    """ Test retry logic for ping attempts (single failure) """
    mocker.patch.object(NetworkPingComparator, '_NetworkPingComparator__ping_network')
    NetworkPingComparator._NetworkPingComparator__ping_network.return_value = [hosts[0]]
    failures = {NETWORK_1: hosts[0]}
    comparator.not_pingable(NETWORK_1, ping_failures=failures)
    assert failures == {NETWORK_1: NetworkPingComparator._NetworkPingComparator__ping_network.return_value}


def test_run(mocker, comparator):
    mocker.patch.object(Process, 'start', return_value=None)
    mocker.patch.object(Process, 'join', return_value=None)
    comparator.run()
    assert isinstance(comparator.ping_failures, BaseProxy)


def test_output_pass(comparator):
    """ Test output for no failures """
    comparator.ping_failures = {NETWORK_1: [], NETWORK_2: []}
    assert comparator.output() == []


def test_output_fail_net1(comparator):
    """ Test output for failure on network 1 """
    comparator.ping_failures = {NETWORK_1: [NETWORK_1.split('0/')[0] + "20"], NETWORK_2: []}
    assert comparator.output() == [NETWORK_1.split('0/')[0] + "20"]


def test_output_fail_net2(comparator):
    """ Test output for failure on network 2 """
    comparator.ping_failures = {NETWORK_1: [], NETWORK_2: [NETWORK_2.split('0/')[0] + "20"]}
    assert comparator.output() == [NETWORK_2.split('0/')[0] + "20"]
