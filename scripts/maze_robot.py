#!/usr/bin/env python

""" This ROS node uses proportional control to guide a robot to a specified
    distance from the obstacle immediately in front of it """

import math
import rospy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header
from nav_msgs.msg import Odometry
from maze_projector import MazeProjector
from geometry_msgs.msg import Twist, Vector3, PointStamped, Point
from maze_solver import MazeSolver
from tf import TransformListener, TransformBroadcaster
from tf.transformations import euler_from_quaternion
from helpers import *

class MazeNavigator(object):
    """ Main controller for the robot maze solver """
    def __init__(self):
        """ Main controller """
        rospy.init_node('maze_navigator')

        self.odom = None
        self.prevOdom = None
        self.scan = []
        self.projected = []

        self.solver = MazeSolver()
        self.listener = TransformListener()
        self.broadcaster = TransformBroadcaster()

        self.counter = 0

        self.currentI = 0 #index to keep track of our instruction
        self.twist = Twist()
        self.laserScan = LaserScan()
        self.turn = True #turning or moving straight

        self.dist_centroid = 0
        self.angle_centroid = 0
        self.point = None
        self.foundHuman = False
        self.foundRealHuman = False
        self.humanThreshhold = .7  # distance that it will detect a human 

        self.maxDistance = .6
        self.wallDistance = .3
        self.nodeDistance = .8 # distance between nodes
        
        #publish robot commands and fake lidar data
        self.pubScan = rospy.Publisher('/maze_scan', LaserScan, queue_size=10)
        self.pubVel = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        self.pubToViz = rospy.Publisher('/centroid', PointStamped, queue_size=10)

        #subscribe to robot position and real lidar data
        rospy.Subscriber('/odom', Odometry, self.callbackOdom)
        rospy.Subscriber('/scan', LaserScan, self.callbackScan)

        self.solver.visualize((0, 0)) 

        
    def callbackScan(self, data):
        """ updates on new scan data
            data: LaserScan data
        """
        if not self.scan:
            self.laserScan = data
        self.scan = data.ranges

    def callbackOdom(self, data):
        """ updates on new odom data
            data: Odometry data
        """
        self.odom = convert_pose_to_xy_and_theta(data.pose)
        if not self.prevOdom: #first reading
            self.prevOdom = self.odom #no change

    def detectHuman(self):
        """ look at the robot's scan and detect where the centroid of the human is 
        """

        # find a cluster of points within certain range
        objectdict = {}
        sumx = 0
        sumy = 0
        for i in range(0, 360):
            if self.scan[i] !=0 and self.scan[i] < self.humanThreshhold:
                locX = self.scan[i]*math.cos(i*math.pi/180.0)
                locY = self.scan[i]*math.sin(i*math.pi/180.0)
                objectdict[i] = [locX, locY]
                sumx += locX
                sumy += locY
        if len(objectdict) !=0: #found a human
            #publish the centroid for rViz
            centroid = [sumx/len(objectdict), sumy/len(objectdict)]
            self.dist_centroid = math.sqrt(centroid[0]**2 + centroid[1]**2)
            self.angle_centroid = math.atan2(centroid[1],centroid[0])
            self.point = PointStamped(point=Point(x=-centroid[0], y=-centroid[1]), header=Header(stamp=rospy.Time.now(), frame_id='base_laser_link'))
            self.foundHuman = True
        else: #no human found
            self.foundHuman = False
        
        if self.foundHuman and self.projected: #compare human location to wall locations
            self.projectedDistance = self.projected[int(self.angle_centroid*180/math.pi)]

            if self.projectedDistance == 0 or self.projectedDistance > self.dist_centroid: #human closer than
                self.foundRealHuman = True
            else: #if human is behind a 'wall'
                self.foundRealHuman = False #no human

        self.foundRealHuman = self.foundRealHuman and self.foundHuman


    def updateNode(self, instruction):
        """ updates visualization and publishes new scan data when a new node is reached
            instruction: new instruction
        """
        self.detectHuman()

        if self.foundRealHuman:
            self.currentI += 1 #increment instruction
            newNode = self.solver.path[self.currentI]
            
            self.turn = True 
            self.prevOdom = self.odom #update odometry
            
            wall = self.getWalls(instruction[1], newNode)
            self.projected = self.projectMaze(wall) #get new laser scan 
            
            stamp = rospy.Time.now()
            self.laserScan.ranges = tuple(self.projectMaze(wall)) #update laser scan
            self.laserScan.header=Header(stamp=rospy.Time.now(),frame_id="base_laser_link")
            fix_map_to_odom_transform(self, stamp, newNode, instruction[1], self.listener, self.broadcaster) #transform coordinate frames
            self.solver.visualize(newNode) #update visualization
        
        else:
            self.twist.linear.x = 0 #stop the robot
            self.twist.angular.z = 0 

    def performInstruction(self):
        """ sets twist and updates maze scan
            based on current instruction and odometry reading
        """
        if not self.odom or not self.prevOdom:
            return

        c = .5 #proportional control constant
        instruction = self.solver.instructions[self.currentI]

        if not self.projected:
            newNode = self.solver.path[self.currentI]
            wall = self.getWalls(instruction[1], newNode)
            self.projected = self.projectMaze(wall) #get new laser scan 

        diffPos, diffAng = self.calcDifference(instruction) #difference in position, difference in angle

        if abs(diffAng)%(2*math.pi) < .05: #turned to correct orientation
            self.turn = False
        
        if abs(diffPos) < .05: #moved forward successfully to next node
            self.updateNode(instruction)

        if self.turn: #set angular velocity
            self.twist.angular.z = c * diffAng
            self.twist.linear.x = 0

        else: #set linear velocity
            self.twist.linear.x = c *diffPos
            self.twist.angular.z = 0

    def calcDifference(self, instruction):
        """ calculate the difference in position and orientation between current and previous odometry
            returns tuple of form (difference in position, difference in orientation)
        """
        
        diffPos = self.nodeDistance - math.sqrt((self.odom[0] - self.prevOdom[0])**2 + (self.odom[1] - self.prevOdom[1])**2)
        diffAng = instruction[0] - angle_diff(self.odom[2],self.prevOdom[2])
        return diffPos, diffAng

    def getWalls(self, orientation, currentNode):
        """ get a representation of maze walls the robot can understand
            currentNode: coordinates of current node
            orientation: current orientation of the robot
            returns: list of length 4 with binary entries
                True is a path
                False is a wall
        """
        neighbors = self.solver.getNeighbors(currentNode)
        walls = [None]*4 #default is all walls
        for nextNode in neighbors:
            nextOrient = self.solver.getNextOrientation(currentNode, nextNode)
            walls[nextOrient] = 1 #update list with True where paths exist
        return walls[orientation:] + walls[:orientation] #rotated depending on robot's position


    def projectMaze(self, wall):
        """ get 'laser scan' ranges for the virtual maze based on surrounding walls
            wall: list with binary entries, output from getWalls
            returns a list of length 359 with maze scan data to be published
        """
        projected = [0]*361

        for i in range(1, 360):
            if i <= 45 or i > 315:
                if not wall[0]:
                   projected[i] = self.wallDistance / math.cos(i*math.pi / 180)
                else:
                    c = 1.0 if i <= 45 else -1.0
                    distance = self.wallDistance / math.sin(i*math.pi / 180) *c
                    projected[i] = 0 if distance > self.maxDistance else distance

            elif i <= 135:
                if not wall[3]:
                    projected[i] = self.wallDistance / math.sin(i*math.pi / 180)
                else:
                    c = 1.0 if i <= 90 else -1.0
                    distance = self.wallDistance /  math.cos(i*math.pi / 180) * c
                    projected[i] = 0 if distance > self.maxDistance else distance

            elif i <= 225:
                if not wall[2]:
                    projected[i] = self.wallDistance / -math.cos(i*math.pi / 180)
                else:
                    c = 1.0 if i <= 180 else -1.0
                    distance = self.wallDistance / math.sin(i*math.pi / 180) *c
                    projected[i] = 0 if distance > self.maxDistance else distance

            elif i <= 315:
                if not wall[1]:
                    projected[i] = self.wallDistance / -math.sin( i*math.pi / 180)
                else:
                    c = -1.0 if i <= 270 else 1.0
                    distance = self.wallDistance / math.cos(i*math.pi / 180)*c
                    projected[i] = 0 if distance > self.maxDistance else distance
        return projected

            
    def run(self):
        """ Our main 5Hz run loop
        """
        r = rospy.Rate(5)
        while not rospy.is_shutdown():
            if self.currentI < len(self.solver.instructions): #still have instructions to perform
                self.performInstruction()
                self.pubScan.publish(self.laserScan) #publish scans
                self.pubVel.publish(self.twist)
                if self.point:
                    self.pubToViz.publish(self.point)
                r.sleep()

            else: 
                self.twist.linear.x = 0 #stop the robot
                self.twist.angular.z = 0
                self.pubVel.publish(self.twist)
                print "done traversing the maze"
                break #exit
            
if __name__ == '__main__':
    node = MazeNavigator()
    node.run()