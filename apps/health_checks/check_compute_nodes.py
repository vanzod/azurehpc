#!/bin/env python3

import argparse
from subprocess import Popen, PIPE, check_output
import json
import os, sys
import time
import datetime
import logging

# Define default logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

def parse_args(args):
    parser = argparse.ArgumentParser(prog='PROG', usage='%(prog)s [options]')
    parser.add_argument("-q", type=str, help="PBS Queue to evaluate")
    parser.add_argument("--debug", action="store_true", help="Print extra information to stdout")
    parser.add_argument("--all_nodes", action="store_true", help="Check all nodes known to PBS")
    parser.add_argument("--ib_tests", action="store_true", help="Run all of the IB tests")
    parser.add_argument("--mem_bw_tests", action="store_true", help="Run a memory bandwidth test on all of the nodes")
    parser.add_argument("--vm_type", type=str, default=None, help="Ex) --vm_type=hbv2")
    parser.add_argument("--wlm", type=str, default="pbs", help="Ex) --wlm=pbs (currently only pbs is supported)")
    args = parser.parse_args(args)

    if args.debug:
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    return(args)

def run_ib_tests(node1=None, node2=None, wlm=None, queue=None):
    if node1 == None or node2 == None or node1 == node2:
        print("Requires two unique nodes to be defined. Node1: {}, Node2: {}".format(node1, node2))
        return False
    if wlm == "pbs":
        sub_cmd = "qsub -N osu_bw_test -joe -l select=1:ncpus=1:mem=10gb:host={}+1:ncpus=1:mem=10gb:host={} -l place=excl ~/apps/health_checks/run_ring_osu_bw_hpcx.pbs".format(node1, node2)
        cmd=sub_cmd.split()
        if queue != None:
            cmd.insert(1,"-q")
            cmd.insert(2, queue)
        logging.debug("Qsub cmd: {}".format(" ".join(cmd)))
        output = check_output(" ".join(cmd), shell=True)
        output = output.decode().strip()
        logging.debug(output)
        return True
    else:
        print("WLM: {} is unsupported".format(wlm))
        return False
    
def run_mem_bw_test(node1=None, wlm=None, queue=None):
    if node1 == None:
        print("Requires one node to be defined. Node1: {}".format(node1))
        return False
    if wlm == "pbs":
        sub_cmd = "qsub -N mem_bw_test -l select=1:ncpus=1:host={} -l place=excl -joe ~/apps/health_checks/run_mem_bw_test.sh".format(node1)
        cmd=sub_cmd.split()
        if queue != None:
            cmd.insert(1,"-q")
            cmd.insert(2, queue)
        logging.debug("Qsub cmd: {}".format(" ".join(cmd)))
        output = check_output(" ".join(cmd), shell=True)
        output = output.decode().strip()
        logging.debug(output)
        return True
    else:
        print("WLM: {} is unsupported".format(wlm))
        return False

def wait_for_jobs_to_finish(check_text=None, wlm=None):
    # Wait for jobs to finish
    if check_text is None:
        logging.debug("No text was entered to check. Exiting function")
        return False
    job_cnt = -1
    while job_cnt != 0 and wlm == "pbs":
        logging.debug("Ready to check output")
        output = check_output("/opt/pbs/bin/qstat -aw | grep {} | wc -l".format(check_text), shell=True)
        job_cnt = int(output)
        logging.debug("Job Count: {}".format(job_cnt))
        print("Remaining Jobs: {:05d}".format(job_cnt), end="\r")
        if job_cnt == 0:
            print()
            return True
        time.sleep(2)
    if wlm is not "pbs":
        print("WLM: {} is not currently supported".format(wlm))
        return False

def check_nodes_for_ib_issues(input=None, check_type=None, cutoff_value=None):
    # Check function inputs
    if input == None:
        logging.warning("Input: {}".format(input))
        return False
    if check_type not in ["latency", "bibw"]: 
        logging.warning("check_type: {} not supported".format(check_type))
        return False
    if cutoff_value == None:
        logging.warning("Cutoff value: {}".format(cutoff_value))
        return False

    # Split the output on \n
    lines = input.split("\n")

    # loop through the nodes to find nodes with poor latency
    results = {}
    for line in lines:
        tmp = line.split()
        if len(tmp) is 0:
            continue
        host1 = tmp[0].split("_")[0]
        host2 = tmp[0].split("_")[2]
        value = tmp[-1].strip()
        logging.debug("Host 1: {}, Host 2: {}, {} Value: {}".format(host1, host2, check_type, value))
        if host1 not in results:
             results[host1] = {host2: {check_type: value}}
        else:
             results[host1][host2] = {check_type: value}
        if host2 not in results:
             results[host2] = {host1: {check_type: value}}
        else:
             results[host2][host1] = {check_type: value}

        check_results = False
        if check_type == "latency":
            check_results = float(value) > cutoff_value
        elif check_type == "bibw":
            check_results = float(value) < cutoff_value

        if check_results:
            if "failures" not in results[host1]:
                results[host1]["failures"]  = 1
            else:
                results[host1]["failures"]  += 1
            if "failures" not in results[host2]:
                results[host2]["failures"]  = 1
            else:
                results[host2]["failures"]  += 1

    logging.debug("Results: {}".format(results))
    return(results)

def check_nodes_for_mem_bw_issues(input=None):
    # Check function inputs
    if input == None:
        logging.warning("Input: {}".format(input))
        return False
    else:
        # Split the output on \n
        input = input.strip()
        lines = input.split("\n")
        if lines == [""]:
            logging.info("All nodes passed the memory bandwidth test")
            return True

    # loop through the nodes to find nodes with poor memory bandwidth
    results = {}
    for line in lines:
        tmp = line.split()
        if len(tmp) is 0:
            continue
        host = tmp[1].strip()
        value = tmp[3].strip()
        logging.warn("{} failed memory bandwidth test: {} MB/s".format(host, value))
        results[host] = {"failures": True, "comment": "low memory bandwidth - {} MB/s".format(value)}
    return(results)

def collect_nodes(wlm="pbs", node_file=None):
    node_info = {}
    if node_file is not None:
        # Read node file and return node info
        return {} 
    
    if wlm == "pbs":
        pbsnodes_cmd = "/opt/pbs/bin/pbsnodes -avS | grep free"
        logging.debug("Find nodes cmd: {}".format(pbsnodes_cmd))
        output = check_output(pbsnodes_cmd, shell=True)
        output = output.decode().strip()
        tmp = output.split("\n")
        logging.debug("Output: {}".format(tmp))
        for line in tmp[0:]:
            logging.debug("Output: {}".format(line))
            if line == "":
                continue
            data = line.split()
            node_info[data[0]] = {"state": data[1], "host": data[4], "queue": data[5]}
        logging.debug("Node Info: {}".format(node_info))
        return(node_info)
    else:
        logging.info("WLM: {} is not supported".format(wlm))
        return {}

if __name__ == "__main__":
    # Read in the script arguments
    logging.debug(sys.argv[1:])
    args = parse_args(sys.argv[1:])

    logging.info("Queue: {}".format(args.q))
    logging.info("All nodes: {}".format(args.all_nodes))
    logging.info("IB tests: {}".format(args.ib_tests))
    logging.info("Mem BW tests: {}".format(args.mem_bw_tests))
    logging.info("VM type: {}".format(args.vm_type))

    # Define the cut off values for different sku types 
    if args.vm_type == None:
        cutoff_latency = 3.0
        cutoff_bibw = 7000
    elif args.vm_type.lower() == "hbv2":
        cutoff_latency = 2.4
        cutoff_bibw = 15000

    # Find all nodes
    node_dict = collect_nodes("pbs")

    nodes = list(node_dict.keys())
    num_of_nodes = len(nodes)
    logging.debug("# of Nodes: {}".format(num_of_nodes))
    logging.debug("Nodes: {}".format(nodes))
    logging.debug("{}".format(node_dict))

    # Make dir to store results
    logging.debug("CWD: {}".format(os.getcwd()))
    new_dir = os.path.join(os.getcwd(), datetime.datetime.now().strftime('Health_tests_%Y%m%d_%H%M%S'))
    os.makedirs(new_dir)
    os.chdir(new_dir)
    logging.debug("CWD: {}".format(os.getcwd()))

    hosts_results = {"latency": {}, "bandwidth": {}}
    ib_results = dict()
    offline_nodes = list()
    recheck_nodes = list()
    if args.ib_tests:
        logging.info("Run IB tests")
        for n_cnt, node in enumerate(nodes):
            node1=node_dict[node]["host"]
            if n_cnt+1 == num_of_nodes:
                node2 = node_dict[nodes[0]]["host"]
            else:
                node2 = node_dict[nodes[n_cnt+1]]["host"]
            logging.debug("Node1: {}, Node2: {}".format(node1, node2))
            run_ib_tests(node1, node2, args.wlm, args.q)
            time.sleep(0.2)

        # Wait for ib jobs to complete
        wait_for_jobs_to_finish("osu_bw_test", args.wlm)

        # Process latency results
        output = check_output('grep -T "^8 " *osu_latency* | sort -n -k 2', shell=True)
        output = output.decode()

        # Check IB for slow latency
        hosts_results["latency"] = check_nodes_for_ib_issues(output, "latency", cutoff_latency)
        logging.info("Latency results: {}".format(hosts_results["latency"]))

        # Check to see if same host was involved in two slow runs
        for host in hosts_results["latency"]:
            if "failures" in hosts_results["latency"][host] and hosts_results["latency"][host]["failures"] > 1:
                logging.warning("Offline host: {}".format(host))
                offline_nodes.append([host, "Slow latency"])
            else:
                logging.info("Run an additional test on host {} to check".format(host))
                recheck_nodes.append([host, "latency"])

        # Process bibw results
        output = check_output('grep -T "^4194304 " *osu_bw.log | sort -n -k 2', shell=True)
        output = output.decode()

        # Check IB for slow latency
        hosts_results["bibw"] = check_nodes_for_ib_issues(output, "bibw", cutoff_bibw)
        logging.info("low ib bandwidth hosts: {}".format(hosts_results["bibw"]))

        # Check to see if same host was involved in two low bandwidth runs
        for host in hosts_results["bibw"]:
            if "failures" in hosts_results["bibw"][host] and hosts_results["bibw"][host]["failures"] == True:
                logging.warning("Offline host: {}".format(host))
                offline_nodes.append([host, "low ib bandwidth"])
            else:
                logging.info("Run an additional test on host {} to check ib bandwidth".format(host))
                recheck_nodes.append([host, "bibw"])
        
        # Process output file results
        output = check_output('grep -T "IB0 Error:" osu_bw_test.o* | sort -n -k 2', shell=True)
        output = output.decode()
        out_lines = output.split("\n")

        # Check for ib0 on host
        if len(out_lines) == 1 and out_lines[0] == "":
            logging.info("All nodes have ib0 reporting in")
        else:
            for line in out_lines:
                tmp = line.split()
                host = tmp[2]
                logging.warn("Offline host: {}".format(host))
                offline_nodes.append([host, "no ib0"])
        
    logging.debug("Recheck nodes: {}".format(recheck_nodes))

    if args.mem_bw_tests:
        logging.info("Run memory bw tests")
        nodes = list(node_dict.keys())
        for node in nodes:
            run_mem_bw_test(node_dict[node]["host"], "pbs")

        # Wait for the jobs to finish 
        wait_for_jobs_to_finish("mem_bw_test", args.wlm)

        # Process results
        output = check_output('grep -T "MB/s Failed" mem_bw_test.[o]* | sort -n -k 2', shell=True)
        output = output.decode()

        # Check for low memory bandwidth
        results = check_nodes_for_mem_bw_issues(output)

    logging.info("Offline nodes: {}".format(offline_nodes))
