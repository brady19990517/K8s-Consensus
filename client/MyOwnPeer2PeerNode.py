from p2pnetwork.node import Node
import ast
import socket
import time

class MyOwnPeer2PeerNode (Node):

    # Python class constructor
    def __init__(self, host, port, id=None, callback=None, max_connections=0):
        super(MyOwnPeer2PeerNode, self).__init__(host, port, id, callback, max_connections)
        print("MyPeer2PeerNode: Started")
        self.message_received= []
        self.xy_storage = {}
        self.z_storage = {}
        self.new_trial = True
        self.server_conn_outbound = None
        self.server_conn_inbound = None

    # all the methods below are called when things happen in the network.
    # implement your network node behavior to create the required functionality.
    def send_to_nodes(self, data, exclude=[]):
        """ Send a message to all the nodes that are connected with this node. data is a python variable which is
            converted to JSON that is send over to the other node. exclude list gives all the nodes to which this
            data should not be sent."""
        self.message_count_send = self.message_count_send + 1
        for n in self.nodes_outbound:
            if n in exclude:
                print("Node send_to_nodes: Excluding node in sending the message")
            else:
                self.send_to_node(n, data)

    def outbound_node_connected(self, node):
        print("outbound_node_connected (" + self.id + "): " + node.id)
        
    def inbound_node_connected(self, node):
        print("inbound_node_connected: (" + self.id + "): " + node.id)

    def node_disconnected(self, node):
        """While the same nodeconnection class is used, the class itself is not able to
           determine if it is a inbound or outbound connection. This function is making
           sure the correct method is used."""
        self.debug_print("node_disconnected: " + node.id)

        if node in self.nodes_inbound:
            del self.nodes_inbound[self.nodes_inbound.index(node)]
            self.inbound_node_disconnected(node)

        if node in self.nodes_outbound:
            del self.nodes_outbound[self.nodes_outbound.index(node)]
            self.outbound_node_disconnected(node)

    def inbound_node_disconnected(self, node):
        print("inbound_node_disconnected: (" + self.id + "): " + node.id)

    def outbound_node_disconnected(self, node):
        print("outbound_node_disconnected: (" + self.id + "): " + node.id)

    def node_message(self, node, data):
        # print("node_message (" + self.id + ") from " + node.id + ": " + str(data))
        init = ast.literal_eval(data)
        if "server_msg" in init:
            self.message_received.append(dict(init["server_msg"]))
        elif "exchange_xy" in init:
            init = dict(init["exchange_xy"])
            iteration = int(list(init.keys())[0])
            if iteration in self.xy_storage:
                self.xy_storage.get(iteration).append(init.get(iteration))
            else:
                self.xy_storage[iteration] = [init.get(iteration)]
        elif "exchange_z" in init:
            init = dict(init["exchange_z"])
            iteration = int(list(init.keys())[0])
            if iteration in self.z_storage:
                self.z_storage.get(iteration).append(float(init.get(iteration)))
            else:
                self.z_storage[iteration] = [float(init.get(iteration))]
        elif "stop" in init:
            self.new_trial = True
            print("[Client] Waiting for current trial to stop...")
            time.sleep(20)
            print("[Client] Resetting parameters for new trial...")
            self.reset()
            

        
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
            if host == socket.gethostbyname('caelum-102'):
                self.server_conn = thread_client

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
    
    def reset(self):
        self.message_received= []
        self.xy_storage = {}
        self.z_storage = {}
        # Disconnect with all outbound nodes except server for a new trial
        try:
            new_outbound_nodes = []
            print("Reset Called")
            for node in self.nodes_outbound:
                print("In the loop")
                if node.id == socket.gethostbyname('caelum-102'):
                    new_outbound_nodes.append(node)
                    continue
                node.stop()
            self.nodes_outbound = new_outbound_nodes
            # Disconnect with all inbound nodes except server for a new trial
            new_inbound_nodes = []
            for node in self.nodes_inbound:
                if node.id == socket.gethostbyname('caelum-102'):
                    new_inbound_nodes.append(node)
                    continue
                node.stop()
            self.nodes_inbound = new_inbound_nodes
        except Exception as e:
            print(e)



    