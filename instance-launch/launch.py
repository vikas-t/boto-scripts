#!/usr/bin/python

# Uses boto3 APIs to fire an AWS EC2 VPC instance with user inputs
# via the commandline
# Relies upon a JSON config per region for the instance attributes

import argparse
import boto3
import botocore
import json
import time
import sys

prefix_sg = 'sg_'


class ec2_instance():
    """
    This wraps all the attributes of an ec2 instance, 
    including tags and elastic IPs
    """

    def __init__(self, region, attributes, vpc_id, name):
        """
        Initialise the class object with the given values
        """
        self.region = region
        self.attributes = attributes
        self.vpc_id = vpc_id
        self.conn = self.connect_to_region()
        self.name = name
        self.entity = None

    def connect_to_region(self):
        """
        Connects to the specified AWS region
        """
        try:
            return boto3.resource('ec2', self.region)
        except botocore.exceptions.ClientError as e:
            print "Error in connecting to region: ", e
            sys.exit(1)

    def execute_setup(self):
        """
        Calls the setup methods in the predefined order
        """
        self.handle_sg()
        # It is to note that an instance has atleast two security
        # groups attached: one that allows SSH access and holds
        # other common rules like port 80, 443 etc, the other
        # SG contains instance specific rules
        entities = self.launch()
        self.entity = entities[0]
        # Yes, we are hanlding only once instance for now
        self.entity.wait_until_running()
        self.entity.reload()
        # Reload the instance resource to update the attributes
        self.show_details()
        self.attach_tags()

    def launch(self):
        """
        Launces the instance with all given attributes in the specified 
        region, returns the instance resource
        """
        try:
            return self.conn.create_instances(**self.attributes)
        except botocore.exceptions.ClientError as e:
            print "Error in creating instance: ", e
            sys.exit(1)

    def handle_sg(self):
        """
        Creates the security group if it does not exist
        """
        instance_sg = prefix_sg + self.name
        # The SG should be identifiable by its name

        for sg in self.conn.security_groups.all():
            if sg.group_name == instance_sg:
                self.attributes['SecurityGroupIds'].append(sg.group_id)
                return
        try:
            response = self.conn.create_security_group(
                GroupName=instance_sg,
                VpcId=self.vpc_id,
                Description='Rules specific to the instance'
            )
            self.attributes['SecurityGroupIds'].append(response.group_id)
        except botocore.exceptions.ClientError as e:
            print "Error: In creating security group", e
            sys.exit(1)

    def attach_tags(self):
        """
        Attaches the tags specified by the user to the instance.
        """
        try:
            self.conn.create_tags(
                Resources=[self.entity.instance_id],
                Tags=[{'Key': 'Name', 'Value': self.name}]
            )
        except botocore.exceptions.ClientError as e:
            print "Error: {}, Could not attach the tags".format(e)

    def attach_eip(self):
        """
        Attaches VPC Elastic IP to the instance
        """
        # FixMe: Complete the function
        pass

    def show_details(self):
        """
        Show attributes of the instance entity
        """
        print "Instance id:", self.entity.instance_id
        print "Instance Public IP address:", self.entity.public_ip_address


def true_dict(data_dict):
    """
    Converts string to boolean type
    """
    for key in data_dict:
        if str(data_dict[key]).lower() == "true":
            data_dict[key] = True
        elif str(data_dict[key]).lower() == "false":
            data_dict[key] = False
        elif type(data_dict[key]) is dict:
            data_dict[key] = true_dict(data_dict[key])
    return data_dict


def main():
    """
    """
    parser = argparse.ArgumentParser(
        description="Launch a new AWS EC2 instance")

    parser.add_argument(
        "-r", "--region", dest="region", required=True,
        help="Region where the instance is fired")

    parser.add_argument(
        "-t", "--type", dest="InstanceType", default="t2.micro",
        help="Size of the instance, default is t2.micro")

    parser.add_argument(
        "-n", "--name", dest="name", required=True,
        help="Name of the instance as visible on console")

    try:
        args = parser.parse_args()
    except:
        parser.print_help()
        sys.exit(1)

    try:
        with open(args.region + '.json') as conf_file:
            conf = json.load(conf_file)
            ec2_defaults = true_dict(conf['ec2_defaults'])
            vpc_id = conf['vpc_id']
    except Exception as e:
        print "Error in reading: ", args.region + '.json'
        print "Error: ", e
        sys.exit(1)
    # For every region where the instance launch is targeted, there should
    # exist a Json config file containing all instance attributes for the
    # instance to launch. For ex: us-west-1.json

    for attr in vars(args):
        if attr in ec2_defaults.keys():
            ec2_defaults[attr] = getattr(args, attr)
    # Overwrite the default instance attributes, feel free to add more
    # arguments in the parser

    instance = ec2_instance(args.region, ec2_defaults, vpc_id, args.name)
    instance.execute_setup()

if __name__ == "__main__":
    main()
