import numpy as np
import pygame as pg
import pygame.locals as pglocs
from math import sin, cos, tan, atan2, sqrt, pi
import random
import time
from collections import deque

# Screen
screen_width = 700
screen_height = 700
screen = pg.display.set_mode([screen_width, screen_height],
                             pglocs.DOUBLEBUF)

# Parameters for robot
def_vel = 0.3  # Default velocity for crazyflie
def_rate = 0.005  # Default angular velocity for crazyflie
dist_thresh = 40  # Paranoid behavior theshold

# Light source
src_pos = np.array([int(screen_width/2), int(screen_height/2)])  # Position
light_std = 0  # Standard deviation for sensor uncertainity
intensity_scaling = 1e5  # Scaling for inverse square law
max_intensity_thresh = 1e4  # Light source declaration at this value

# Circular obstacles
num_obsts = 5
obsts_min_radius = 20
obsts_max_radius = 60


def constrain(angle):
    '''
    Constrains given angle to [0, 2pi]
    '''
    while (angle < 0):
        angle += 2*pi
    while (angle >= 2*pi):
        angle -= 2*pi
    return angle


def simulate_light_sensor(robot_pos, src_pos, std_dev):
    '''
    Simulates light sensor.
    Inputs - [robot.x, robot.y], [src.x, src.y], std_deviation
    Returns - Light intensity (inverse square to distance, with noise)
    '''
    robot_x = robot_pos[0]
    robot_y = robot_pos[1]
    src_x = src_pos[0]
    src_y = src_pos[1]
    dist = sqrt((robot_x - src_x)**2 + (robot_y - src_y)**2)
    return intensity_scaling/(dist**2) + random.gauss(0, std_dev)


def simulate_rangefinder(robot, obsts):
    '''
    Simulates rangefinder.
    Inputs - robot object, list of all obstacle objects
    Returns - [left_dist, front_dist, right_dist, back_dist]
    '''
    xr = robot.x
    yr = robot.y
    phi_r = robot.phi

    dist = []  # Left, front, right, back
    angles = [phi_r - pi/2, phi_r,
              phi_r + pi/2, phi_r + pi]  # Angles of the 4 sensors
    for phi in angles:
        # Constrain angles within [0, 2pi]
        phi = constrain(phi)

        obsts_dists = []  # Will hold distances to all obstacles hit by beam
        for i in range(len(obsts)):
            xo = obsts[i].x
            yo = obsts[i].y
            r = obsts[i].r
            # Intersection of beam with obstacle
            # Solve beam eqn with obstacle circle eqn
            # Quadratic in x coordinate. Coeffs for ax^2+bx+c=0:
            a = 1 + (tan(phi))**2
            b = 2*(tan(phi)*(yr-xr*tan(phi)) - xo - yo*tan(phi))
            c = (yr-xr*tan(phi))*(yr-xr*tan(phi)-2*yo) + xo**2 + yo**2 - r**2
            if(b**2 - 4*a*c == 0):  # Beam is tangent to obstacle
                # Coords of point where beam hits obstacle
                xhit = -b/(2*a)
                yhit = xhit*tan(phi) + yr - xr*tan(phi)  # From eqn of beam
                # Check if obstacle is in front of the sensor
                dot_prod = cos(phi)*(xo-xr) + sin(phi)*(yo-yr)
                if(dot_prod > 0):
                    obsts_dists.append(sqrt((xr-xhit)**2 + (yr-yhit)**2))
            elif(b**2 - 4*a*c > 0):  # Beam hits two points on obstacle
                # Coords of points where beam hits obstacle
                xhit1 = (-b + sqrt(b**2-4*a*c))/(2*a)
                xhit2 = (-b - sqrt(b**2-4*a*c))/(2*a)
                yhit1 = xhit1*tan(phi) + yr - xr*tan(phi)  # From eqn of beam
                yhit2 = xhit2*tan(phi) + yr - xr*tan(phi)  # From eqn of beam
                dist1 = sqrt((xr-xhit1)**2 + (yr-yhit1)**2)
                dist2 = sqrt((xr-xhit2)**2 + (yr-yhit2)**2)
                # Check if obstacle is in front of the sensor
                dot_prod = cos(phi)*(xo-xr) + sin(phi)*(yo-yr)
                if(dot_prod > 0):
                    obsts_dists.append(min(dist1, dist2))  # Closer point
        if(len(obsts_dists) > 0):  # Beam hits one or more obstacles
            dist.append(min(obsts_dists))  # Choose closest obstacle
        else:  # Beam hits room walls
            if(phi < pi/2 or phi > 3*pi/2):  # Beam facing right wall
                # Coords of point where beam hits right edge
                xhit = screen_width
                yhit = xhit*tan(phi) + yr - xr*tan(phi)  # From eqn of beam
                if(yhit >= 0 and yhit <= screen_height):  # Hits r-wall in room
                    dist.append(sqrt((xr-xhit)**2 + (yr-yhit)**2))
                else:  # Beam hits top or bottom wall
                    if(yhit > screen_height):  # Beam hits bottom wall
                        # Coords of point where beam hits bottom wall
                        yhit = screen_height
                        xhit = xr + (yhit-yr)/(tan(phi))  # From eqn of beam
                    else:  # Beam hits top wall
                        # Coords of point where beam hits top wall
                        yhit = 0
                        xhit = xr - yr/tan(phi)  # From equation of beam
                    dist.append(sqrt((xr-xhit)**2 + (yr-yhit)**2))
            elif(phi > pi/2 and phi < 3*pi/2):  # Beam facing left edge
                # Coords of point where beam hits left edge
                xhit = 0
                yhit = yr - xr*tan(phi)  # From equation of beam
                if(yhit >= 0 and yhit <= screen_width):  # Hits l-wall in room
                    dist.append(sqrt((xr-xhit)**2 + (yr-yhit)**2))
                else:  # Beam hits top or bottom wall
                    if(yhit > screen_height):  # Beam hits bottom wall
                        # Coords of point where beam hits bottom wall
                        yhit = screen_height
                        xhit = xr + (yhit-yr)/(tan(phi))  # From eqn of beam
                    else:  # Beam hits top wall
                        yhit = 0
                        xhit = xr - yr/tan(phi)  # From equation of beam
                    dist.append(sqrt((xr-xhit)**2 + (yr-yhit)**2))
            elif(phi == pi/2):  # Beam directly towards bottom wall
                dist.append(screen_height - yr)
            elif(phi == 3*pi/2):  # Beam directly facing towards top wall
                dist.append(yr)

    return dist


def pgloop(inputs, t=0.010):
    '''
    PyGame loop
    '''
    v = inputs[0]
    dir_x = inputs[1]
    dir_y = inputs[2]
    omega = inputs[3]
    init_time = time.time()
    while(time.time() < init_time + t):  # Do this for t seconds
        event = pg.event.poll()
        # Pause if SPC is pressed
        if(event.type == pglocs.KEYDOWN and event.key == pglocs.K_SPACE):
            while(1):
                event = pg.event.poll()
                if(event.type == pglocs.KEYDOWN and
                   event.key == pglocs.K_SPACE):
                    break  # Resume if SPC pressed again
                time.sleep(0.010)  # Wait for 10 ms
        screen.fill((50, 55, 60))  # background

        draw()

        # Update robot attributes
        bot.x += v*dir_x
        bot.y += v*dir_y
        bot.phi = constrain(bot.phi + omega)
        bot.tip = [int(bot.x + bot.length * cos(bot.phi)),
                   int(bot.y + bot.length * sin(bot.phi))]
        bot.bottom = [int(bot.x - bot.length * cos(bot.phi)),
                      int(bot.y - bot.length * sin(bot.phi))]
        bot.bottom_l = [int(bot.bottom[0] - bot.breadth * sin(bot.phi)),
                        int(bot.bottom[1] + bot.breadth * cos(bot.phi))]
        bot.bottom_r = [int(bot.bottom[0] + bot.breadth * sin(bot.phi)),
                        int(bot.bottom[1] - bot.breadth * cos(bot.phi))]
        bot.intensity_last = bot.intensity

        # Update multiranger attributes
        distances = simulate_rangefinder(bot, obsts)
        mr.x = bot.x
        mr.y = bot.y
        mr.phi = bot.phi
        mr.ld = distances[0]
        mr.fd = distances[1]
        mr.rd = distances[2]
        mr.bd = distances[3]
        mr.lpoint = np.array([mr.x+mr.ld*cos(mr.phi - pi/2),
                              mr.y+mr.ld*sin(mr.phi - pi/2)])
        mr.fpoint = np.array([mr.x+mr.fd*cos(mr.phi),
                              mr.y+mr.fd*sin(mr.phi)])
        mr.rpoint = np.array([mr.x+mr.rd*cos(mr.phi + pi/2),
                              mr.y+mr.rd*sin(mr.phi + pi/2)])
        mr.bpoint = np.array([mr.x+mr.bd*cos(mr.phi + pi),
                              mr.y+mr.bd*sin(mr.phi + pi)])

        # Update obstacle attributes
        # for i in range(num_obsts):
        #     obsts[i].x += int(1.5 * sin(0.02*pg.time.get_ticks()))
        #     obsts[i].y += int(1.5 * sin(0.02*pg.time.get_ticks()))

        # FPS. Print if required
        # clock.tick(300)     # To limit fps, controls speed of the animation
        # fps = (frames*1000)/(pg.time.get_ticks() - ticks)  # calculate fps

        # Update PyGame display
        pg.display.flip()
        # frames+=1


class robot():
    def __init__(self, init_pos, init_ang, size):
        '''
        Args: [init_x, init_y], init_ang, [l, b]
        '''
        self.x = init_pos[0]
        self.y = init_pos[1]
        self.pos = [self.x, self.y]
        self.phi = init_ang
        self.intensity = random.random()
        self.intensity_last = 0
        self.length = size[0]
        self.breadth = size[1]

        self.tip = [int(self.x + self.length * cos(self.phi)),
                    int(self.y + self.length * sin(self.phi))]
        self.bottom = [int(self.x - self.length * cos(self.phi)),
                       int(self.y - self.length * sin(self.phi))]
        self.bottom_l = [int(self.bottom[0] - self.breadth * sin(self.phi)),
                         int(self.bottom[1] + self.breadth * cos(self.phi))]
        self.bottom_r = [int(self.bottom[0] + self.breadth * sin(self.phi)),
                         int(self.bottom[1] - self.breadth * cos(self.phi))]

    def show(self):
        '''
        Draw robot to the screen
        '''
        # Robot
        pg.draw.polygon(screen, (255, 0, 0),
                        [self.tip, self.bottom_l, self.bottom_r], 0)
        # Center pt
        pg.draw.circle(screen, (250, 180, 0), [int(self.x), int(self.y)], 1)

    def run(self):
        '''
        Run controller
        '''
        pgloop(bot.start_forward())

    def tumble(self, ang=1.5):
        '''
        Tumble controller
        '''
        if(random.random() <= 0.5):
            pgloop(bot.start_turn_right(), ang*random.random())
        else:
            pgloop(bot.start_turn_left(), ang*random.random())
        pgloop(bot.start_forward())

    def avoid_obst(self, mrindex):
        '''
        Avoid obstacle controller
        '''
        if(mrindex == 0):  # Smallest dist sensed from left
            pgloop(bot.start_right(), 0.1)
            pgloop(bot.start_turn_right())
            pgloop(bot.start_forward())
        elif(mrindex == 1):  # Smallest dist sensed from front
            pgloop(bot.start_back(), 0.1)
            pgloop(bot.start_turn_right())
            pgloop(bot.start_forward())
        elif(mrindex == 2):  # Smallest dist sensed from right
            pgloop(bot.start_left(), 0.1)
            pgloop(bot.start_turn_left())
            pgloop(bot.start_forward())
        else:  # Smallest dist sensed from back
            pgloop(bot.start_forward())

    ########################################
    # Crazyflie client methods
    ########################################
    # Unimplemented take_off(), land(), wait()

    # Velocity control commands
    ####################
    # Unimplemented:
    # start_up(), start_down()
    # start_circle_left(), start_circle_right()

    def start_left(self, velocity=def_vel):
        '''
        Start moving left
        '''
        theta = constrain(self.phi - pi/2)
        dir_x = cos(theta)
        dir_y = sin(theta)
        omega = 0
        return [velocity, dir_x, dir_y, omega]

    def start_right(self, velocity=def_vel):
        '''
        Start moving right
        '''
        theta = constrain(self.phi + pi/2)
        dir_x = cos(theta)
        dir_y = sin(theta)
        omega = 0
        return [velocity, dir_x, dir_y, omega]

    def start_forward(self, velocity=def_vel):
        '''

        Start moving forward
        '''
        theta = constrain(self.phi)
        dir_x = cos(theta)
        dir_y = sin(theta)
        omega = 0
        return [velocity, dir_x, dir_y, omega]

    def start_back(self, velocity=def_vel):
        '''

        Start moving backward
        '''
        theta = constrain(self.phi - pi)
        dir_x = cos(theta)
        dir_y = sin(theta)
        omega = 0
        return [velocity, dir_x, dir_y, omega]

    def stop(self):
        '''
        STOP!
        '''
        velocity = 0
        dir_x = 0
        dir_y = 0
        omega = 0
        return [velocity, dir_x, dir_y, omega]

    def start_turn_left(self, rate=def_rate):
        '''
        Start turning left
        '''
        velocity = 0
        dir_x = 0
        dir_y = 0
        omega = -rate
        return [velocity, dir_x, dir_y, omega]

    def start_turn_right(self, rate=def_rate):
        '''
        Start turning right
        '''
        velocity = 0
        dir_x = 0
        dir_y = 0
        omega = rate
        return [velocity, dir_x, dir_y, omega]

    def start_linear_motion(self, vel_x, vel_y):
        '''
        Start a linear motion
        Positive X is forward
        Positive Y is left
        '''
        velocity = sqrt(vel_x**2 + vel_y**2)
        theta = constrain(self.phi - atan2(vel_y, vel_x))
        dir_x = cos(theta)
        dir_y = sin(theta)
        omega = 0
        return [velocity, dir_x, dir_y, omega]


class obstacle():
    def __init__(self, radius, pos):
        '''
        Args: radius, [pos_x, pos_y]
        '''
        self.r = radius
        self.x = pos[0]
        self.y = pos[1]

    def show(self):
        pg.draw.circle(screen, (0, 0, 255), (self.x, self.y), self.r, 0)


class multiranger():
    def __init__(self, robot, dists):
        '''
        Args: robot object, [left_dist, front_dist, right_dist, back_dist]
        '''
        self.x = robot.x
        self.y = robot.y
        self.phi = robot.phi
        self.ld = dists[0]
        self.fd = dists[1]
        self.rd = dists[2]
        self.bd = dists[3]
        self.lpoint = np.array([self.x+self.ld*cos(self.phi - pi/2),
                                self.y+self.ld*sin(self.phi - pi/2)])
        self.fpoint = np.array([self.x+self.fd*cos(self.phi),
                                self.y+self.fd*sin(self.phi)])
        self.rpoint = np.array([self.x+self.rd*cos(self.phi + pi/2),
                                self.y+self.rd*sin(self.phi + pi/2)])
        self.bpoint = np.array([self.x+self.bd*cos(self.phi + pi),
                                self.y+self.bd*sin(self.phi + pi)])

    def show(self):
        '''
        Draw multiranger beams to the screen
        '''
        # Left sensor
        pg.draw.line(screen, (250, 180, 0), [int(self.x), int(self.y)],
                     [int(self.lpoint[0]), int(self.lpoint[1])], 2)
        # Front sensor
        pg.draw.line(screen, (250, 180, 0), [int(self.x), int(self.y)],
                     [int(self.fpoint[0]), int(self.fpoint[1])], 2)
        # Right sensor
        pg.draw.line(screen, (250, 180, 0), [int(self.x), int(self.y)],
                     [int(self.rpoint[0]), int(self.rpoint[1])], 2)
        # Back sensor
        pg.draw.line(screen, (250, 180, 0), [int(self.x), int(self.y)],
                     [int(self.bpoint[0]), int(self.bpoint[1])], 2)


# Create obstacles
obsts = []
radius = []
obsts_x = []
obsts_y = []
for i in range(num_obsts):
    radius.append(random.randint(obsts_min_radius, obsts_max_radius))
    obsts_x.append(random.randint(radius[i], screen_width - radius[i]))
    obsts_y.append(random.randint(radius[i], screen_height - radius[i]))
for i in range(num_obsts):
    obsts.append(obstacle(radius[i], [obsts_x[i], obsts_y[i]]))

robot_x = 100  # Initial position
robot_y = 600  # Initial position
robot_phi = 5  # Initial angle
robot_l = 15  # Robot length
robot_b = 6  # Robot width

# Initialize objects
bot = robot([robot_x, robot_y], robot_phi,
            [robot_l, robot_b])
distances = simulate_rangefinder(bot, obsts)
mr = multiranger(bot, distances)


def draw():
    '''
    Draw stuff to PyGame screen
    '''
    # Threshold radius
    pg.draw.circle(screen, (100, 100, 100),
                   (int(bot.x), int(bot.y)),
                   dist_thresh, 0)
    # Constant intensity circles
    pg.draw.circle(screen, (250, 250, 250), src_pos, 20, 1)
    pg.draw.circle(screen, (200, 200, 200), src_pos, 50, 1)
    pg.draw.circle(screen, (150, 150, 150), src_pos, 100, 1)
    pg.draw.circle(screen, (100, 100, 100), src_pos, 150, 1)
    pg.draw.circle(screen, (60, 60, 60), src_pos, 200, 1)
    pg.draw.circle(screen, (40, 40, 40), src_pos, 250, 1)
    # Multiranger beams
    mr.show()
    # Robot
    bot.show()
    # Obstacles
    for i in range(len(obsts)):
        obsts[i].show()
    # Light source
    pg.draw.circle(screen, (0, 255, 0), src_pos, 8, 0)


def main():
    '''
    The main function
    '''
    # PyGame inits
    pg.init()
    pg.display.set_caption('Run and tumble simulation')
    # clock = pg.time.Clock()
    # ticks = pg.time.get_ticks()
    # frames = 0

    # Commands
    while(bot.intensity < max_intensity_thresh):
        # Read light intensity
        bot.intensity = simulate_light_sensor([bot.x, bot.y],
                                              src_pos, light_std)

        # The Finite State Machine #
        # If no obsts in dist_thresh, run-and-tumble
        if(mr.ld > dist_thresh and mr.fd > dist_thresh and
           mr.rd > dist_thresh and mr.bd > dist_thresh):
            # If intensity is increasing, run
            if(bot.intensity > bot.intensity_last):
                bot.run()
            # Else tumble to random direction
            else:
                bot.tumble()
        # Obst(s) detected within dist_thresh. Run away from closest obst
        else:
            # Closest dist sensed among the 4 directions
            mrmin = min(mr.ld, mr.fd, mr.rd, mr.bd)
            mrindex = [mr.ld, mr.fd, mr.rd, mr.bd].index(mrmin)
            bot.avoid_obst(mrindex)

    # If intensity >= max_intensity_thresh, stop
    pgloop(bot.stop())

    # Congratulatory screen
    time.sleep(3)
    screen.fill((50, 55, 60))  # background
    font = pg.font.SysFont("Hack", 72)
    success_text = font.render("SUCCESS!!!", True, (0, 128, 0))
    screen.blit(success_text,
                ((screen_width - success_text.get_width())//2,
                    (screen_height - success_text.get_height())//2))
    pg.display.flip()
    time.sleep(3)


if(__name__ == '__main__'):
    main()
