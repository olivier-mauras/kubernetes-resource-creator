#!/usr/bin/env python3

import os
import sys
import jinja2
import json
import kubernetes
from kubernetes.client.rest import ApiException
from pprint import pprint
import yaml

SUPPORTED_EVENT_TYPES = ['Event', 'Synchronization']

def get_crd(cluster_config, operator_name, resType):
    with kubernetes.client.ApiClient(cluster_config) as api_client:
        api_instance = kubernetes.client.CustomObjectsApi(api_client)
        group = 'krc.io'
        version = 'v1'
        plural = 'operators'
        name = operator_name
        try:
            api_response = api_instance.get_cluster_custom_object(group, version, plural, name)
            if 'spec' in api_response:
                if resType in api_response['spec']:
                    resources = api_response['spec'][resType]
                else:
                    print('Missing %s entry in CRD spec definition' % resType)
                    sys.exit(1)
            else:
                print('Invalid CRD spec definition')
                sys.exit(1)
            return resources
        except ApiException as e:
            print("Exception when calling CustomObjectsApi->get_cluster_custom_object: %s\n" % e)
            sys.exit(1)


def process_resources(context, resources, kubernetes_patch_path):
    # Event has only one object
    if context['type'] == 'Event':
        # Retrieve values from object to process resources templates if needed
        obj = context.get('object')
        write_patch_path(kubernetes_patch_path, obj, resources)

    if context['type'] == 'Synchronization':
        obj = context.get('objects')
        write_patch_path(kubernetes_patch_path, obj, resources, True)


def write_patch_path(patch_file, obj, resources, synchronization=False):
    concatened_yaml = ''
    for resource in resources:
        if synchronization:
            # Synchronization mode we should loop over all objects
            for o in obj:
                object_ = o.get('object')
                jinja_augmented = jinja2.Template(resources[resource]).render(object=object_)
                concatened_yaml = concatened_yaml + '\n' + jinja_augmented
        else:
            jinja_augmented = jinja2.Template(resources[resource]).render(object=obj)
            concatened_yaml = concatened_yaml + '\n' + jinja_augmented

    yaml_dump = yaml.dump_all(yaml.safe_load_all(concatened_yaml))
    with open(patch_file, 'w') as k8s_rsc:
        k8s_rsc.write(yaml_dump)


def main():
    # Load our operator name from env variable HOOK_OPERATOR_NAME
    operator_name = os.getenv('HOOK_OPERATOR_NAME', default=None)
    if operator_name is None:
        print('Error: No HOOK_OPERATOR_NAME variable found')
        sys.exit(1)

    # Load kubernetes client config
    cluster_config = kubernetes.config.load_incluster_config()

    # Check how the script is called
    if len(sys.argv)>1 and sys.argv[1] == "--config":
        # Return hook config
        config = get_crd(cluster_config, operator_name, 'config')
        print(config)
    else:
        # Retrieve BINDING_CONTEXT_PATH and exit in error if not found
        binding_context_path = os.getenv('BINDING_CONTEXT_PATH', default=None)
#        print(binding_context_path)
        if binding_context_path is None:
            print('Error: No BINDING_CONTEXT_PATH variable found')
            sys.exit(1)

        # Retrieve KUBERNETES_PATCH_PATH and exit in error if not found
        kubernetes_patch_path = os.getenv('KUBERNETES_PATCH_PATH', default=None)
#        print(kubernetes_patch_path)
        if kubernetes_patch_path is None:
            print('Error: No KUBERNETES_PATCH_PATH variable found')
            sys.exit(1)

        # Read BINDING_CONTEXT_PATH
        with open(binding_context_path, 'r') as event:
            binding_context = json.loads(event.read())
#        # TMP file to fetch context
#        with open('/tmp/tmp.json', 'w') as tmp:
#            tmp.write(binding_context)

        # Check type in binding_context
        # If 'Synchronization' we'll have an objects array to loop on.
        # If 'Event' we'll only have one event object
        if 'type' in binding_context[0]:
            # Check if type is supported
            if binding_context[0]['type'] in SUPPORTED_EVENT_TYPES:
                # Retrieve resources to deploy from CRD
                resources = get_crd(cluster_config, operator_name, 'resources')

                # Process resources
                process_resources(binding_context[0], resources, kubernetes_patch_path)
            else:
                print('Warning: type %s not supported, will not do anything' % binding_context[0]['type'])
                sys.exit(0)
        else:
            print('Error: type not found in binding context')
            with open('/tmp/tmp.json', 'w') as tmp:
                tmp.write(binding_context[0])
            sys.exit(1)


if __name__ == "__main__":
    main()
