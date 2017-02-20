#!/usr/bin/env python

# Filename: start.py
# Description:
# This is the start script to be run by the student.
# Note:
# 1. It needs 'start.config' file, where
#    <labname> is given as a parameter to the script.
# 2. If the lab has multiple containers and/or multi-home
#    networking, then <labname>.network file is necessary
#

import glob
import json
import md5
import os
import re
import subprocess
import sys
import time
import zipfile
from netaddr import *
import ParseMulti
import ParseStartConfig

LABS_ROOT = os.path.abspath("../../labs/")

# Error code returned by docker inspect
SUCCESS=0
FAILURE=1

def isalphadashscore(name):
    # check name - alphanumeric,dash,underscore
    if re.match(r'^[a-zA-Z0-9_-]*$', name):
        return True
    else:
        return False

# get docker0 IP address
def getDocker0IPAddr():
    command="ifconfig docker0 | awk '/inet addr:/ {print $2}' | sed 's/addr://'"
    #print "Command to execute is (%s)" % command
    child = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = child.stdout.read().strip()
    #print "Result of subprocess.Popen getDocket0IPAddr is %s" % result
    return result

# Parameterize my_container_name container
def ParameterizeMyContainer(mycontainer_name, container_user, lab_instance_seed, user_email, labname):
    #print "About to call parameterize.sh with LAB_INSTANCE_SEED = (%s)" % lab_instance_seed
    command = 'docker exec -it %s script -q -c "/home/%s/.local/bin/parameterize.sh %s %s %s %s" /dev/null' % (mycontainer_name, container_user, lab_instance_seed, user_email, labname, mycontainer_name)
    #print "Command to execute is (%s)" % command
    result = subprocess.call(command, shell=True)
    #print "Result of subprocess.call ParameterizeMyContainer is %s" % result
    return result

# Start my_container_name container
def StartMyContainer(mycontainer_name):
    command = "docker start %s 2> /dev/null" % mycontainer_name
    #print "Command to execute is (%s)" % command
    result = subprocess.call(command, shell=True)
    #print "Result of subprocess.call StartMyContainer is %s" % result
    return result

# Check to see if my_container_name container has been created or not
def IsContainerCreated(mycontainer_name):
    command = "docker inspect -f {{.Created}} %s 2> /dev/null" % mycontainer_name
    #print "Command to execute is (%s)" % command
    result = subprocess.call(command, shell=True)
    #print "Result of subprocess.call IsContainerCreated is %s" % result
    return result

def ConnectNetworkToContainer(mycontainer_name, mysubnet_name, mysubnet_ip):
    #print "Connecting more network subnet to container %s" % mycontainer_name
    command = "docker network connect --ip=%s %s %s 2> /dev/null" % (mysubnet_ip, mysubnet_name, mycontainer_name)
    #print "Command to execute is (%s)" % command
    result = subprocess.call(command, shell=True)
    #print "Result of subprocess.call ConnectNetworkToContainer is %s" % result
    return result

def CreateSingleContainerNonDefault(mycontainer_name, mycontainer_image_name, mysubnet_name, mysubnet_ip):
    #print "Create Single Container with non-default networking"
    docker0_IPAddr = getDocker0IPAddr()
    #print "getDockerIPAddr result (%s)" % docker0_IPAddr
    createsinglecommand = "docker create -t --network=%s --ip=%s --privileged --add-host my_host:%s --name=%s %s bash" % (mysubnet_name, mysubnet_ip, docker0_IPAddr, mycontainer_name, mycontainer_image_name)
    #print "Command to execute is (%s)" % createsinglecommand
    result = subprocess.call(createsinglecommand, shell=True)
    #print "Result of subprocess.call CreateSingleContainerNonDefault is %s" % result
    return result

def CreateSingleContainerDefault(mycontainer_name, mycontainer_image_name):
    #print "Create Single Container with default networking"
    docker0_IPAddr = getDocker0IPAddr()
    #print "getDockerIPAddr result (%s)" % docker0_IPAddr
    createsinglecommand = "docker create -t --privileged --add-host my_host:%s --name=%s %s bash" % (docker0_IPAddr, mycontainer_name, mycontainer_image_name)
    #print "Command to execute is (%s)" % createsinglecommand
    result = subprocess.call(createsinglecommand, shell=True)
    #print "Result of subprocess.call CreateSingleContainerDefault is %s" % result
    return result

def DoStartSingle(start_config, labname):
    #print "Do: START Single Container with default networking"
    container_name  = start_config.containers["default"]["full_name"]
    container_image = start_config.containers["default"]["image_name"]
    container_user  = start_config.containers["default"]["user"]
    host_home_xfer  = start_config.conf["host_home_xfer"]
    lab_master_seed = start_config.conf["lab_master_seed"]
    haveContainer   = IsContainerCreated(container_name)
    #print "IsContainerCreated result (%s)" % haveContainer

    # Set need_seeds=False first
    need_seeds=False

    # IsContainerCreated returned FAILURE if container does not exists
    if haveContainer == FAILURE:
        # Container does not exist, create the container
        containerCreated = CreateSingleContainerDefault(container_name, container_image)
        #print "CreateSingleContainerDefault result (%s)" % containerCreated
        # If we just create it, then set need_seeds=True
        need_seeds=True
        # Give the container some time -- just in case
        time.sleep(3)

    # Check again - 
    haveContainer = IsContainerCreated(container_name)
    #print "IsContainerCreated result (%s)" % haveContainer

    # IsContainerCreated returned FAILURE if container does not exists
    if haveContainer == FAILURE:
        sys.stderr.write("ERROR: DoStartSingle Container %s still not created!\n" % container_name)
        sys.exit(1)
    else:
        # Start the container
        start_result = StartMyContainer(container_name)
        if start_result == FAILURE:
            sys.stderr.write("ERROR: DoStartSingle Container %s failed to start!\n" % container_name)
            sys.exit(1)

    # If the container is just created, prompt user's e-mail
    # then parameterize the container
    if need_seeds:
        # Prompt user for e-mail address
        user_email = raw_input("Please enter your e-mail address: ")
        # Create hash using LAB_MASTER_SEED concatenated with user's e-mail
        # LAB_MASTER_SEED is per laboratory - specified in start.config
        string_to_be_hashed = '%s:%s' % (lab_master_seed, user_email)
        mymd5 = md5.new()
        mymd5.update(string_to_be_hashed)
        mymd5_hex_string = mymd5.hexdigest()
        #print mymd5_hex_string

        parameterize_result = ParameterizeMyContainer(container_name, container_user, mymd5_hex_string,
                                                      user_email, labname)
        if parameterize_result == FAILURE:
            sys.stderr.write("ERROR: Failed to parameterize lab container %s!\n" % container_name)
            sys.exit(1)

    # Reach here - Everything is OK - spawn two terminals by default
    spawn_command = "gnome-terminal -x docker exec -it %s bash -l &" % container_name
    os.system(spawn_command)
    os.system(spawn_command)

    return 0

# Create SUBNETS
def CreateSubnets(subnets):
    #print "Inside CreateSubnets"
    #for (subnet_name, subnet_network_mask) in networklist.iteritems():
    for subnet_name in subnets:
        subnet_network_mask = subnets[subnet_name].subnet_mask
        #print "subnet_name is %s" % subnet_name
        #print "subnet_network_mask is %s" % subnet_network_mask

        command = "docker network inspect %s > /dev/null" % subnet_name
        #print "Command to execute is (%s)" % command
        inspect_result = subprocess.call(command, shell=True)
        #print "Result of subprocess.call CreateSubnets docker network inspect is %s" % inspect_result
        if inspect_result == FAILURE:
            # Fail means does not exist - then we can create
            if subnets[subnet_name].subnet_gateway != None:
                subnet_gateway = subnets[subnet_name].subnet_gateway
                command = "docker network create -d bridge --gateway=%s --subnet %s %s 2> /dev/null" % (subnet_gateway, subnet_network_mask, subnet_name)
            else:
                command = "docker network create -d bridge --subnet %s %s 2> /dev/null" % (subnet_network_mask, subnet_name)
            #print "Command to execute is (%s)" % command
            create_result = subprocess.call(command, shell=True)
            #print "Result of subprocess.call CreateSubnets docker network create is %s" % create_result
            if create_result == FAILURE:
                sys.stderr.write("ERROR: Failed to create %s subnet at %s!\n" % (subnet_name, subnet_network_mask))
                sys.exit(1)
        else:
            print "Already exists! Not creating %s subnet at %s!\n" % (subnet_name, subnet_network_mask)
        

def DoStartMultiple(start_config, labname, net_config_path):
    host_home_xfer = start_config.conf["host_home_xfer"]
    lab_master_seed = start_config.conf["lab_master_seed"]
    #print "Do: START Multiple Containers and/or multi-home networking"
    docker0_IPAddr = getDocker0IPAddr()
    #print "getDockerIPAddr result (%s)" % docker0_IPAddr

    multi_config = ParseMulti.ParseMulti(net_config_path)

    # Create SUBNETS
    CreateSubnets(multi_config.subnets)

    for mycontainer_name in multi_config.containers:
        mycontainer_image_name = multi_config.containers[mycontainer_name].container_image
        nickname = mycontainer_name.split(".")[1]
        container_user = start_config.containers[nickname]["user"]

        haveContainer = IsContainerCreated(mycontainer_name)
        #print "IsContainerCreated result (%s)" % haveContainer

        # Set need_seeds=False first
        need_seeds=False

        # IsContainerCreated returned FAILURE if container does not exists
        if haveContainer == FAILURE:
            first_subnet_for_container = True
            for mysubnet_name in multi_config.containers[mycontainer_name].container_nets:
                mysubnet_ip = multi_config.containers[mycontainer_name].container_nets[mysubnet_name].ipaddr
                # First subnet must be part of docker create
                if first_subnet_for_container:
                    first_subnet_for_container = False
                    # Container does not exist, create the container
                    # Use CreateSingleContainerNonDefault()
                    #print "My subnet name is %s" % mysubnet_name
                    #print "My subnet ip is %s" % mysubnet_ip
                    containerCreated = CreateSingleContainerNonDefault(mycontainer_name, mycontainer_image_name,
                                             mysubnet_name, mysubnet_ip)
                    #print "CreateSingleContainerNonDefault result (%s)" % containerCreated
                    # Give the container some time -- just in case
                    time.sleep(3)
                    # If we just create it, then set need_seeds=True
                    need_seeds=True
                    first_subnet_for_container = False
                else:
                # Subsequent subnet must use docker network connect
                    #print "My subnet name is %s" % mysubnet_name
                    #print "My subnet ip is %s" % mysubnet_ip
                    connectNetworkResult = ConnectNetworkToContainer(mycontainer_name, mysubnet_name, mysubnet_ip)

        # Check again - 
        haveContainer = IsContainerCreated(mycontainer_name)
        #print "IsContainerCreated result (%s)" % haveContainer

        # IsContainerCreated returned FAILURE if container does not exists
        if haveContainer == FAILURE:
            sys.stderr.write("ERROR: DoStartMultiple Container %s still not created!\n" % mycontainer_name)
            sys.exit(1)
        else:
            # Start the container
            start_result = StartMyContainer(mycontainer_name)
            if start_result == FAILURE:
                sys.stderr.write("ERROR: DoStartMultiple Container %s failed to start!\n" % container_name)
                sys.exit(1)

        # If the container is just created, prompt user's e-mail
        # then parameterize the container
        if need_seeds:
            # Prompt user for e-mail address
            user_email = raw_input("Please enter your e-mail address: ")
            # Create hash using LAB_MASTER_SEED concatenated with user's e-mail
            # LAB_MASTER_SEED is per laboratory - specified in start.config
            string_to_be_hashed = '%s:%s' % (lab_master_seed, user_email)
            mymd5 = md5.new()
            mymd5.update(string_to_be_hashed)
            mymd5_hex_string = mymd5.hexdigest()
            #print mymd5_hex_string
    
            parameterize_result = ParameterizeMyContainer(mycontainer_name, container_user, mymd5_hex_string,
                                                          user_email, labname)
            if parameterize_result == FAILURE:
                sys.stderr.write("ERROR: Failed to parameterize lab container %s!\n" % mycontainer_name)
                sys.exit(1)
    
    # Reach here - Everything is OK - spawn terminal for each container based on num_terminal
    for mycontainer_name in multi_config.containers:
        num_terminal = multi_config.containers[mycontainer_name].term
        #print "Number of terminal is %d" % num_terminal
        # If the number of terminal is zero -- do not spawn
        if num_terminal != 0:
            for x in range(0, num_terminal):
                spawn_command = "gnome-terminal -x docker exec -it %s bash -l &" % mycontainer_name
                os.system(spawn_command)

    return 0


# Check existence of /home/$USER/$HOST_HOME_XFER directory - create if necessary
def CreateHostHomeXfer(host_xfer_dir):
    # remove trailing '/'
    host_xfer_dir = host_xfer_dir.rstrip('/')
    #print "host_home_xfer directory (%s)" % host_xfer_dir
    if os.path.exists(host_xfer_dir):
        # exists but is not a directory
        if not os.path.isdir(host_xfer_dir):
            # remove file then create directory
            os.remove(host_xfer_dir)
            os.makedirs(host_xfer_dir)
        #else:
        #    print "host_home_xfer directory (%s) exists" % host_xfer_dir
    else:
        # does not exists, create directory
        os.makedirs(host_xfer_dir)

# Usage: start.py <labname>
# Arguments:
#    <labname> - the lab to start
def main():
    #print "start.py -- main"
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: start.py <labname>\n")
        sys.exit(1)
    
    labname = sys.argv[1]
    mycwd = os.getcwd()
    myhomedir = os.environ['HOME']
    #print "current working directory for %s" % mycwd
    #print "current user's home directory for %s" % myhomedir
    #print "ParseStartConfig for %s" % labname
    lab_path          = os.path.join(LABS_ROOT,labname)
    config_path       = os.path.join(lab_path,"config") 
    start_config_path = os.path.join(config_path,"start.config")
    net_config_path   = os.path.join(config_path,labname + ".network")
   
    start_config = ParseStartConfig.ParseStartConfig(start_config_path, labname, "student")

    # Check existence of /home/$USER/$HOST_HOME_XFER directory - create if necessary
    host_xfer_dir = '%s/%s' % (myhomedir, start_config.host_home_xfer)
    CreateHostHomeXfer(host_xfer_dir)

    # If <labname>.network exists, do multi-containers/multi-home networking
    # else do single container with default networking
    if not os.path.exists(net_config_path):
        DoStartSingle(start_config, labname)
    else:
        DoStartMultiple(start_config, labname, net_config_path)

    return 0

if __name__ == '__main__':
    sys.exit(main())

