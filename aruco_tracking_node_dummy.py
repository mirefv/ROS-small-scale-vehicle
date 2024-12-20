#!/usr/bin/env python3

import socket
import time
import math
import struct
import re


class ViconTrackerUtils:
    def __init__(self):
        self.FRAME_NUMBER_OFFSET = 0
        self.FRAME_NUMBER_SIZE = 4
        self.ITEMS_IN_BLOCK_SIZE = 1
        self.OBJECT_ID_SIZE = 1
        self.ITEM_DATA_SIZE_SIZE = 2
        self.OBJECT_NAME_SIZE = 24
        self.TRANSLATION_SIZE = 8
        self.ROTATION_SIZE = 8
        self.OBJECT_ID_OFFSET = self.FRAME_NUMBER_OFFSET + self.FRAME_NUMBER_SIZE + self.ITEMS_IN_BLOCK_SIZE
        self.ITEM_DATA_SIZE_OFFSET = self.OBJECT_ID_OFFSET + self.OBJECT_ID_SIZE
        self.OBJECT_NAME_OFFSET = self.ITEM_DATA_SIZE_OFFSET + self.ITEM_DATA_SIZE_SIZE
        self.TRANSLATION_X_OFFSET = 32
        self.TRANSLATION_Y_OFFSET = 40
        self.TRANSLATION_Z_OFFSET = 48
        self.ROTATION_X_OFFSET = 56
        self.ROTATION_Y_OFFSET = 64
        self.ROTATION_Z_OFFSET = 72

    def parse_translation(self, data):
        translation_x = struct.unpack("<d", data[self.TRANSLATION_X_OFFSET:self.TRANSLATION_X_OFFSET + 8])[0]
        translation_y = struct.unpack("<d", data[self.TRANSLATION_Y_OFFSET:self.TRANSLATION_Y_OFFSET + 8])[0]
        translation_z = struct.unpack("<d", data[self.TRANSLATION_Z_OFFSET:self.TRANSLATION_Z_OFFSET + 8])[0]
        return translation_x, translation_y, translation_z

    def parse_rotation(self, data):
        rotation_x_rad = struct.unpack("<d", data[self.ROTATION_X_OFFSET:self.ROTATION_X_OFFSET + 8])[0]
        rotation_y_rad = struct.unpack("<d", data[self.ROTATION_Y_OFFSET:self.ROTATION_Y_OFFSET + 8])[0]
        rotation_z_rad = struct.unpack("<d", data[self.ROTATION_Z_OFFSET:self.ROTATION_Z_OFFSET + 8])[0]
        return rotation_x_rad, rotation_y_rad, rotation_z_rad

    def parse_frame_number(self, data):
        frame_number = struct.unpack("<I", data[self.FRAME_NUMBER_OFFSET:self.FRAME_NUMBER_OFFSET + self.FRAME_NUMBER_SIZE])[0]
        return frame_number

    def parse_object_id(self, data):
        object_id = struct.unpack("<B", data[self.OBJECT_ID_OFFSET:self.OBJECT_ID_OFFSET + self.OBJECT_ID_SIZE])[0]
        return object_id

    def parse_object_name(self, data):
        object_name = data[self.OBJECT_NAME_OFFSET:self.OBJECT_NAME_OFFSET + self.OBJECT_NAME_SIZE].decode().rstrip('\x00')
        # Replace invalid characters and convert to lowercase
        #object_name = re.sub(r'[^a-zA-Z0-9_]', '_', object_name).lower()
        object_name = re.sub(r'[^a-zA-Z0-9_]', '_', object_name)
        return object_name


class For_convertion_utils():
    def __init__(self,size_factor,x_map_shift,y_map_shift,angle_shift):
        self.size_factor=size_factor
        self.x_map_shift=x_map_shift
        self.y_map_shift=y_map_shift
        self.angle_shift=angle_shift
    
    def real2sim_xyzypr(self,pose,orientation):
        x=pose[0]*self.size_factor+self.x_map_shift
        y=pose[1]*self.size_factor+self.y_map_shift
        angle=-orientation[2]+self.angle_shift
        return [x,y,angle]

    def sim2real_xyzypr(self,pose,orientation):
        x=(pose[0]-self.x_map_shift)/self.size_factor
        y=(pose[2]-self.x_map_shift)/self.size_factor
        angle=-(orientation[1]-self.angle_shift)
        return [x,y,angle]
    
    def real2sim_xyp(self,pose):
        x,y,p=pose
        x=x*self.size_factor+self.x_map_shift
        y=y*self.size_factor+self.y_map_shift
        angle=-p+self.angle_shift
        return [x,y,angle]

    def sim2real_xyp(self,pose):
        x,y,p=pose
        x=(x-self.x_map_shift)/self.size_factor
        y=(y-self.y_map_shift)/self.size_factor
        angle=-(p-self.angle_shift)
        return [x,y,angle]

SIZE_FACTOR=7.33
X_MAP_SHIFT=48
Y_MAP_SHIFT=50
ANGLE_SHIFT=0


class Status:
    def __init__(self):
        self.is_running = True
        self.real_pose = [0.0, 0.0, 0.0]
        self.real_orientation = [0.0, 0.0, 0.0]
        self.real_speed = 0.0


import socket
import json
import time
import math

def udp_parse_data_json(data):
    # Remove padding and decode JSON
    json_data = data.rstrip(b'\x00').decode('utf-8')
    # Check if JSON is complete
    if not json_data.endswith("}"):
        print("Incomplete JSON data received, skipping this packet.")
        return None
    # Try to parse JSON
    try:
        data_dict = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None
    return data_dict

def tracking_node():
    print("Tracking node running")

    status = Status()
    last_update_time = time.time()
    last_position = None
    tracking_ip = '0.0.0.0'
    tracking_port = 51001
    for_conversions = For_convertion_utils(SIZE_FACTOR, X_MAP_SHIFT, Y_MAP_SHIFT, ANGLE_SHIFT)

    # Initialize socket connection
    vicon = ViconTrackerUtils()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((tracking_ip, tracking_port))
    print("Connection established successfully")

    while status.is_running:
        data, _ = sock.recvfrom(256)
        print("Got data")

        data_dict=udp_parse_data_json(data)
        if data_dict==None:
            pass

        # Retrieve the number of items and the items themselves
        items_in_block = data_dict.get("items_count", 0)
        items = data_dict.get("items", [])

        # Loop through each item in the received JSON data
        for item in items:
            name = item.get("name", "")
            translation = item.get("translation", [0.0, 0.0, 0.0])
            rotation = item.get("rotation", [0.0, 0.0, 0.0])

            # Process data if the object is "Donkey"
            if name == "Donkey":
                x, y, z = [coord / 1000 for coord in translation]  # Convert mm to meters
                status.real_pose = [x, y, z]
                status.real_orientation = rotation

                # Calculate speed if there was a previous position
                if last_position is not None:
                    current_time = time.time()
                    time_diff = current_time - last_update_time
                    if time_diff > 0:  # Avoid division by zero
                        speed_x = (x - last_position[0]) / time_diff
                        speed_y = (y - last_position[1]) / time_diff
                        speed_z = (z - last_position[2]) / time_diff
                        speed = math.sqrt(speed_x ** 2 + speed_y ** 2)
                        status.real_speed = speed
                        # Publish real speed of the car (if needed)
                        # speed_pub.publish(speed)

                # Update last position and time
                last_position = [x, y, z]
                last_update_time = time.time()

            # Print out the details for each object
            print(f"Object: {name}")
            print(f"x: {translation[0] / 1000}")
            print(f"y: {translation[1] / 1000}")
            if name == "Donkey":
                print(f"s: {status.real_speed}")
            print(f"a: {math.degrees(rotation[2])}")



    print("[TRACKING CLIENT]: QUIT")


if __name__ == '__main__':
    tracking_node()