from math import sqrt
from time import sleep
import rospy
import tf2_ros
from geometry_msgs.msg import TransformStamped

class SetpointPublisher:

    def __init__(self):
        self.done = False
        self.setpoint_index = 0 
        self.setpoint_frame = rospy.get_param('~setpoint_frame')
        self.setpoint_radius = rospy.get_param('~setpoint_radius') # meters
        self.use_tf = rospy.get_param('~use_tf', True)

        setpoints_file_path = rospy.get_param('~setpoints_file_path')
        self.setpoints = self.getSetpointsFromFile(setpoints_file_path)
        setpoint_topic = rospy.get_param('~setpoint_topic', 'setpoints')
        self.setpoint_pub = rospy.Publisher(setpoint_topic, TransformStamped, queue_size=10)
        self.tfbroadcaster = tf2_ros.TransformBroadcaster()

        self.setpoint_msg = TransformStamped()
        self.setpoint_msg.header.frame_id = self.setpoint_frame
        self.setpoint_msg.child_frame_id = "setpoint"
        self.updateSetpointMsg()

        init_time = rospy.get_param('~init_time', 0)
        sleep(init_time)

        if self.use_tf:
            self.tfparent_frame = rospy.get_param('~tfparent_frame')
            self.tfchild_frame = rospy.get_param('~tfchild_frame')
            self.tfbuffer = tf2_ros.Buffer(cache_time = rospy.Duration(1))
            self.tflistener = tf2_ros.TransformListener(self.tfbuffer)
            self.nav_pose_msg = TransformStamped()
            nav_pose_out_topic = rospy.get_param('~nav_pose_out_topic', 'nav_pose')
            self.nav_pose_out_pub = rospy.Publisher(nav_pose_out_topic, TransformStamped, queue_size=10);
        else:
            pose_topic = rospy.get_param('~pose_topic')
            self.pose_sub = rospy.Subscriber(pose_topic, TransformStamped, self.callback)

    def getSetpointsFromFile(self, setpoints_file_path):
        # get setpoints from textfile, [pos_x, pos_y, pos_z, ori_x, ori_y, ori_z, ori_w]
        with open(setpoints_file_path) as txtfile:
            setpoints = [[float(value) for value in line.strip("\n").split()] for line in txtfile.readlines()]
        return setpoints 

    def distance(self, current_position, setpoint_position):
        distance = sqrt(sum([(a - b)**2 for a, b in zip(current_position, setpoint_position)]))
        rospy.logdebug_throttle(.5, rospy.get_name() + ': client is ' + str(distance) + ' m away from target.')
        return distance
    
    def distanceXY(self, current_position, setpoint_position):
        return self.distance(
            [current_position[0], current_position[1]], 
            [setpoint_position[0], setpoint_position[1]])

    def distanceXZ(self, current_position, setpoint_position):
        return self.distance(
            [current_position[0], current_position[2]], 
            [setpoint_position[0], setpoint_position[2]])

    def evaluate(self, current_position):
        active_setpoint = self.setpoints[self.setpoint_index]

        if self.distance(current_position, active_setpoint[0:3]) < self.setpoint_radius:
            if self.setpoint_index < len(self.setpoints)-1:
                self.changeActiveSetpoint(self.setpoint_index + 1)
                self.updateSetpointMsg()
                rospy.logdebug(rospy.get_name() + ' setpoint changed to: ' + str(self.setpoints[self.setpoint_index]))
            else:
                self.nav_pose_msg.header.frame_id = "Path_Complete"
                self.nav_pose_msg.child_frame_id = "Path_Complete"
                self.nav_pose_msg.header.stamp = rospy.Time.now()                
                self.nav_pose_out_pub.publish(self.nav_pose_msg)
                self.done = True


    def changeActiveSetpoint(self, new_index):
        self.setpoint_index = new_index

    def updateSetpointMsg(self):
        active_setpoint = self.setpoints[self.setpoint_index]
        self.setpoint_msg.transform.translation.x = active_setpoint[0]
        self.setpoint_msg.transform.translation.y = active_setpoint[1]
        self.setpoint_msg.transform.translation.z = active_setpoint[2]
        self.setpoint_msg.transform.rotation.x = active_setpoint[3]
        self.setpoint_msg.transform.rotation.y = active_setpoint[4]
        self.setpoint_msg.transform.rotation.z = active_setpoint[5]
        self.setpoint_msg.transform.rotation.w = active_setpoint[6]

    def callback(self, msg):
        translation = msg.transform.translation
        current_position = [translation.x, translation.y, translation.z]
        self.evaluate(current_position)

    def updateUsingTF(self):
            try:
                transform_msg = self.tfbuffer.lookup_transform(self.tfparent_frame, self.tfchild_frame, rospy.Time(0))
                position = [
                    transform_msg.transform.translation.x, 
                    transform_msg.transform.translation.y, 
                    transform_msg.transform.translation.z]                
                self.nav_pose_msg.transform.translation.x = transform_msg.transform.translation.x
                self.nav_pose_msg.transform.translation.y = transform_msg.transform.translation.y
                self.nav_pose_msg.transform.translation.z = transform_msg.transform.translation.z
                self.nav_pose_msg.transform.rotation.x = transform_msg.transform.rotation.x
                self.nav_pose_msg.transform.rotation.y = transform_msg.transform.rotation.y
                self.nav_pose_msg.transform.rotation.z = transform_msg.transform.rotation.z
                self.nav_pose_msg.transform.rotation.w = transform_msg.transform.rotation.w
                self.nav_pose_msg.header.frame_id = self.tfparent_frame
                self.nav_pose_msg.child_frame_id = self.tfchild_frame
                self.nav_pose_msg.header.stamp = rospy.Time.now()                
                self.nav_pose_out_pub.publish(self.nav_pose_msg)
                self.evaluate(position)
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                return

    def publishSetpoint(self):
        self.setpoint_msg.header.stamp = rospy.Time.now()
        self.setpoint_pub.publish(self.setpoint_msg)

        if hasattr(self, 'tfbroadcaster'):
            self.tfbroadcaster.sendTransform(self.setpoint_msg)

    def run(self):
        while (not rospy.is_shutdown()) and (not self.done):
            if self.use_tf:
                self.updateUsingTF()

            self.publishSetpoint()
            rospy.Rate(100).sleep()

if __name__ == '__main__':

    rospy.init_node('setpoint_publisher')
    setpoint_publisher = SetpointPublisher()
    setpoint_publisher.run()