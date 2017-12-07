from math import sqrt
from time import sleep
import rospy
import tf
from geometry_msgs.msg import TransformStamped

class SetpointPublisher:

    def __init__(self):
        self.setpoint_index = 0
        self.setpoint_msg = TransformStamped()
        setpoints_file_path = rospy.get_param('~setpoints_file_path')
        self.setpoints = self.getSetpointsFromFile(setpoints_file_path)
        setpoint_topic = rospy.get_param('~setpoint_topic', 'setpoints')
        self.setpoint_pub = rospy.Publisher(setpoint_topic, TransformStamped, queue_size=10)
        self.setpoint_radius = rospy.get_param('~setpoint_radius', 0.1) # meters
        init_time = rospy.get_param('~init_time', 0)
        sleep(init_time)

        self.use_tf = rospy.get_param('~use_tf', False)
        if self.use_tf:
            self.tfparent_frame = rospy.get_param('~tfparent_frame', 'world')
            self.tfchild_frame = rospy.get_param('~tfchild_frame', 'camera')
            self.tflistener = tf.TransformListener()
        else:
            pose_topic = rospy.get_param('~pose_topic', 'pose')
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

    def evaluate(self, current_position):
        active_setpoint = this.setpoints[self.setpoint_index]

        if self.distance(current_position, active_setpoint[0:3]) < self.setpoint_radius:
            if self.setpoint_index < len(self.setpoints)-1:
                self.changeActiveSetpoint(self.setpoint_index + 1)
                self.updateSetpointMsg()
                rospy.logdebug(rospy.get_name() + ' setpoint changed to: ' + str(self.setpoints[self.setpoint_index]))        

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
        if self.tflistener:
            try:
                [position, orientation] = self.tflistener.lookupTransform(self.tfparent_frame, self.tfchild_frame, rospy.Time(0))
            except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
                return
            self.evaluate(position)
        else:
            raise RuntimeError('No tf::Listener has been instantiated!')

    def publishSetpointMsg(self):
        self.setpoint_msg.header.stamp = rospy.Time.now()
        self.setpoint_pub.publish(self.setpoint_msg)

    def run(self):
        while not rospy.is_shutdown():
            if self.use_tf:
                self.updateUsingTF()

            self.publishSetpointMsg()
            rospy.Rate(100).sleep()

if __name__ == '__main__':

    rospy.init_node('setpoint_publisher')
    setpoint_publisher = SetpointPublisher()
    setpoint_publisher.run()