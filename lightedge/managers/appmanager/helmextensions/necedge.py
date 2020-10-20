#!/usr/bin/env python3
#
# Copyright (c) 2020 Giovanni Baggio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

"""NEC Edge extension."""

import os
import json
import yaml
import requests
import logging

from lightedge.managers.appmanager.helmextensions.publisher import *

from helmpythonclient.client import HelmPythonClient

broker_endpoint = "activemq-service.default.svc.cluster.local:5672"
topic = "NetworkServiceIP"


class NECEdge(HelmPythonClient):

    message_to_publish = {}

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.root = dict()   
        self.releases = dict()


    def list(self, **kwargs):

        return self._get_releases(), None

    def install(self, release_name, chart_name, app_host=False, upgrade=False, **kwargs):

        chart_dir = self.default_chart_dir
        if 'chart_dir' in kwargs:
            chart_dir = kwargs['chart_dir']

        if app_host:
            self.root[release_name] = app_host

        chart_path = '%s/%s' % (chart_dir, chart_name)
        command = [self.helm, "template", release_name, chart_path]
        k8s_code, err = self._run_command(command)

        json_docs = []
        yaml_docs = yaml.load_all(k8s_code)
        for doc in yaml_docs:
            json_docs.append(doc)

        if upgrade:
            url = "%s/api/v1/update/app/%s" % (self.root[release_name], release_name)
            response = requests.put(url, json=json_docs)
        else:
            url = "%s/api/v1/create/app/%s" % (self.root[release_name], release_name)
            response = requests.post(url, json=json_docs)

        logging.info("WITHIN INSTALL self.root %s" % (self.root)) 
        logging.info("STATUS CODE FROM EC %s" % (response.status_code))
        #logging.info("JSON FROM EC %s" % (json.loads(response.text))

        if response.status_code != 200:
            raise ValueError("Error from NEC Edge API")


        """ Getting Pod's IP address and publishing on the broker """
        response_list = json.loads(response.text)
        logging.info("RESPONSE LIST %s" % (response_list))

        for ns_element in response_list:
            for pod_name, pod_ip in ns_element.items():
                if release_name in pod_name:
                    ns_ip = pod_ip

                    self.message_to_publish[release_name] = ns_ip
                    logging.info("Publishing IP %s of NS %s" % (ns_ip, release_name))

                    self.publish_ip(self.message_to_publish)



        release = {"k8s_code": k8s_code,
                   "chart_dir": chart_dir,
                   "status": "deployed"}
        self.releases[release_name] = release

        return release, None

    def uninstall(self, release_name,  **kwargs):

        logging.info("WITHIN UNINSTALL self.root %s" % (self.root)) 

        url = "%s/api/v1/delete/app/%s" % (self.root[release_name], release_name)
        response = requests.delete(url)

        if response.status_code != 200:
            raise ValueError("Error from NEC Edge API")

        del self.message_to_publish[release_name]
        logging.info("Deleting IP of %s" % (release_name))
        self.publish_ip(self.message_to_publish)


        del self.releases[release_name]
        return None, None

    def status(self, release_name, **kwargs):

        return self._get_release(release_name), None

    def get_values(self, release_name, **kwargs):

        release = self.releases[release_name]
        raw, _ = self.show_info(release_name, "values",
                                chart_dir=release["chart_dir"])
        values = yaml.load(raw, yaml.SafeLoader)
        return values, None

    def _get_releases(self):

        out_releases = []

        for release_name in self.releases:
            out_release = self._get_release(release_name, extended=False)
            out_releases.append(out_release)

        return out_releases

    def _get_release(self, release_name, extended=True):

        release_data = self.releases[release_name]

        out_release = dict()
        out_release["name"] = release_name
        out_release["status"] = release_data["status"]
        if extended:
            out_release["k8s_code"] = release_data["k8s_code"]

        return out_release

    def publish_ip(self, publish_msg): 
   
        client = Producer(broker_endpoint, topic, publish_msg)
        container = Container(client)
        events = EventInjector()
        container.selectable(events)

        qpid_thread = Thread(target=container.run)
        qpid_thread.start()

        logging.info("DONE PUBLISHING!!!") 