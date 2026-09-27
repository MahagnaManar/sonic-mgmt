import logging
import time
import pytest

pytestmark = [
    pytest.mark.topology("t0", "t1")
]

logger = logging.getLogger(__name__)


def test_static_route_performance(rand_selected_dut):
    duthost = rand_selected_dut

    bgp_neighbors = duthost.show_and_parse("show ip bgp summary")
    nexthop = bgp_neighbors[0]["neighbhor"]

    prefixes = [f"100.0.{i}.0/24" for i in range(1, 11)]
    total = len(prefixes)

    logger.info("===== Static route performance test on %s: %d routes via %s =====",
                duthost.hostname, total, nexthop)

    routes_removed = False
    try:
        start_time = time.time()

        logger.info("===== Adding %d static routes =====", total)
        for i, prefix in enumerate(prefixes, 1):
            logger.info("Adding route %d/%d: %s", i, total, prefix)
            duthost.shell(
                f"config route add prefix {prefix} nexthop {nexthop}"
            )

        timeout = 120

        logger.info("===== Waiting for routes to appear in 'show ip route' =====")
        while True:
            route_output = duthost.shell("show ip route")["stdout"]

            missing = [prefix for prefix in prefixes if prefix not in route_output]

            if not missing:
                break

            elapsed = time.time() - start_time
            logger.info("Waiting... %d/%d routes visible (elapsed %.1fs)",
                        total - len(missing), total, elapsed)

            if elapsed > timeout:
                pytest.fail(f"Timeout: {len(missing)} static routes did not appear: {missing}")

            time.sleep(1)

        add_time = time.time() - start_time
        logger.info("All %d routes visible after %.2f seconds", total, add_time)

        resource_output = duthost.shell("top -b -n 1 | head -n 20")["stdout"]
        logger.info("DUT resource usage after adding routes:\n%s", resource_output)

        remove_start_time = time.time()

        logger.info("===== Removing %d static routes =====", total)
        for i, prefix in enumerate(prefixes, 1):
            logger.info("Removing route %d/%d: %s", i, total, prefix)
            duthost.shell(
                f"config route del prefix {prefix} nexthop {nexthop}"
            )

        logger.info("===== Waiting for routes to disappear from 'show ip route' =====")
        while True:
            route_output = duthost.shell("show ip route")["stdout"]

            remaining = [prefix for prefix in prefixes if prefix in route_output]

            if not remaining:
                break

            elapsed = time.time() - remove_start_time
            logger.info("Waiting... %d/%d routes still present (elapsed %.1fs)",
                        len(remaining), total, elapsed)

            if elapsed > timeout:
                pytest.fail(f"Timeout: {len(remaining)} static routes were not removed: {remaining}")

            time.sleep(1)

        remove_time = time.time() - remove_start_time
        routes_removed = True

        logger.info("===== Summary =====")
        logger.info("Time for all %d routes to appear:    %.2f seconds", total, add_time)
        logger.info("Time for all %d routes to disappear: %.2f seconds", total, remove_time)
        logger.info("===== Test PASSED =====")

    finally:
        # Safety cleanup
        if not routes_removed:
            logger.warning("Test did not complete, cleaning up static routes")
            for prefix in prefixes:
                duthost.shell(
                    f"config route del prefix {prefix} nexthop {nexthop}",
                    module_ignore_errors=True
                )
