from __future__ import print_function, unicode_literals
from proton import Message
from proton.handlers import MessagingHandler
from proton.reactor import ApplicationEvent, Container, EventInjector

from sys import argv
from time import sleep
from threading import Thread

import logging 

##


class Producer(MessagingHandler):

    

    def __init__(self, server, send_topic, send_message, ns_ip=False):
        super(Producer, self).__init__()
        self.server = server
        self.send_topic = send_topic
        self.sender = None
        self.send_message = send_message
        self.ns_ip = ns_ip

    def on_start(self, event):
        conn = event.container.connect(self.server)
        self.sender = event.container.create_sender(conn, 'topic://%s' % self.send_topic)

    def on_sendable(self, event):

        if ns_ip is not False:
            logging.info("Send IP of %s" % (self.ns_ip.keys())) 
            self.send_message[self.ns_ip.keys()] = self.ns_ip.values()

        message = Message(body=self.send_message)

        self.sender.send(message)

        
