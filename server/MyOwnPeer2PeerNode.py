from p2pnetwork.node import Node
import ast
import socket
import time

class MyOwnPeer2PeerNode (Node):

    # Python class constructor
    def __init__(self, host, port, id=None, callback=None, max_connections=0):
        super(MyOwnPeer2PeerNode, self).__init__(host, port, id, callback, max_connections)
        print("MyPeer2PeerNode: Started")
        self.client_hostname_list = []
        self.message_received = []
        self.flag_storage = []
        self.z_storage = []
        self.start_consensus_time = None
        self.start_consensus_flag = False

    # all the methods below are called when things happen in the network.
    # implement your network node behavior to create the required functionality.
    def send_to_nodes(self, data, exclude=[]):
        """ Send a message to all the nodes that are connected with this node. data is a python variable which is
            converted to JSON that is send over to the other node. exclude list gives all the nodes to which this
            data should not be sent."""
        self.message_count_send = self.message_count_send + 1
        # for n in self.nodes_inbound:
        #     if n in exclude:
        #         self.debug_print("Node send_to_nodes: Excluding node in sending the message")
        #     else:
        #         self.send_to_node(n, data)
        for n in self.nodes_outbound:
            if n in exclude:
                self.debug_print("Node send_to_nodes: Excluding node in sending the message")
            else:
                self.send_to_node(n, data)

    def outbound_node_connected(self, node):
        print("outbound_node_connected (" + self.id + "): " + node.id)
        return None
        
    def inbound_node_connected(self, node):
        print("inbound_node_connected: (" + self.id + "): " + node.id)
        self.client_hostname_list.append(node.id)

    def inbound_node_disconnected(self, node):
        """This method is invoked when a node, that was previously connected with us, is in a disconnected
           state."""
        self.debug_print("inbound_node_disconnected: " + node.id)
        if self.callback is not None:
            self.callback("inbound_node_disconnected", self, node, {})

    def outbound_node_disconnected(self, node):
        # print("outbound_node_disconnected: (" + self.id + "): " + node.id)
        return None

    def node_message(self, node, data):
        init = ast.literal_eval(data)
        if "client_msg" in init:
            # print("node_message (" + self.id + ") from " + node.id + ": " + str(data))
            init = list(init["client_msg"])
            client = str(init[0])
            iteration = int(init[1])
            flag = int(init[2])
            z = float(init[3])
            self.flag_storage[iteration][client]=flag
            self.z_storage[iteration][client]=z
        elif "start_consensus" in init and self.start_consensus_flag==False:
            self.start_consensus_time = time.time()
            self.start_consensus_flag = True
        
    def node_disconnect_with_outbound_node(self, node):
        print("node wants to disconnect with oher outbound node: (" + self.id + "): " + node.id)
        
    def node_request_to_stop(self):
        print("node is requested to stop (" + self.id + "): ")

    def connect_with_node(self, host, port, reconnect=False):
        """ Make a connection with another node that is running on host with port. When the connection is made, 
            an event is triggered outbound_node_connected. When the connection is made with the node, it exchanges
            the id's of the node. First we send our id and then we receive the id of the node we are connected to.
            When the connection is made the method outbound_node_connected is invoked. If reconnect is True, the
            node will try to reconnect to the code whenever the node connection was closed. The method returns
            True when the node is connected with the specific host."""

        if host == self.host and port == self.port:
            print("connect_with_node: Cannot connect with yourself!!")
            return False

        # Check if node is already connected with this node!
        for node in self.nodes_outbound:
            if node.host == host and node.port == port:
                print("connect_with_node: Already connected with this node (" + node.id + ").")
                return True

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.debug_print("connecting to %s port %s" % (host, port))
            sock.connect((host, port))

            # Basic information exchange (not secure) of the id's of the nodes!
            sock.send(self.id.encode('utf-8')) # Send my id to the connected node!
            connected_node_id = sock.recv(4096).decode('utf-8') # When a node is connected, it sends its id!

            # Cannot connect with yourself
            if self.id == connected_node_id:
                print("connect_with_node: You cannot connect with yourself?!")
                sock.send("CLOSING: Already having a connection together".encode('utf-8'))
                sock.close()
                return True

            thread_client = self.create_new_connection(sock, connected_node_id, host, port)
            thread_client.start()

            self.nodes_outbound.append(thread_client)
            self.outbound_node_connected(thread_client)

            # If reconnection to this host is required, it will be added to the list!
            if reconnect:
                self.debug_print("connect_with_node: Reconnection check is enabled on node " + host + ":" + str(port))
                self.reconnect_to_nodes.append({
                    "host": host, "port": port, "tries": 0
                })

            return True

        except Exception as e:
            self.debug_print("TcpServer.connect_with_node: Could not connect with node. (" + str(e) + ")")
            return False

    def param_init(self, max_iter):
        self.z_storage = [None] * max_iter
        self.flag_storage = [None] * max_iter
        for i in range(max_iter):
            self.flag_storage[i] = {}
            self.z_storage[i] = {}
            for client in self.client_hostname_list:
                self.flag_storage[i][client] = -1

    def reset(self):
        self.message_received= []
        self.flag_storage = []#List of dictionary
        self.z_storage = []#List of dictionary
        self.start_consensus_time = None
        self.start_consensus_flag = False