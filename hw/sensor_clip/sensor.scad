// Fine detail
$fa = 0.5;
$fs = 0.5;

// Coarse detail
//$fa = 1.0;
//$fs = 1.5;

sensor_width = 34;
sensor_thick = 2.5;
sensor_corner_radius = 8;

edge_width = 3;      // width of 3 sides
top_width = 7;     // width of 4 side

tongue_width = 8; // width of tongue running to U shape (also bottom of U)

u_total_width =  22; // width of outsides of U shape
u_height = 16;       // height of U shape
u_y_offset = 3;      // vertical offset of U shape
u_bar_width = 4;     // width of vertical bars of U shape
u_radius = 4;        // radius @ top of vertical bars of U shape


fudge = 1; // used to make subtractive area a little thicker
hole_x = sensor_width - 2 * edge_width;
hole_y = sensor_width - edge_width - top_width;

module rounded_square(x, y, z, corner_radius) {
  union()
  {
    radius_offset_x = x / 2 - corner_radius;
    radius_offset_y = y / 2 - corner_radius;

    // 4 corners from circles
    translate([radius_offset_x,radius_offset_y,0])           cylinder(r=corner_radius, h=z);
    translate([-1 * radius_offset_x,radius_offset_y,0])      cylinder(r=corner_radius, h=z);
    translate([radius_offset_x,-1 * radius_offset_y,0])      cylinder(r=corner_radius, h=z);
    translate([-1 * radius_offset_x,-1 *radius_offset_y,0])  cylinder(r=corner_radius, h=z);

    // fill in the middle with bars
    translate([0,0,(z/2)])  cube([x,2*radius_offset_y,z],center=true);
    translate([0,0,(z/2)])  cube([2*radius_offset_x, y,z],center=true);
  }
}

// Sensor
color([0.7,0.7,0.7]) union()
{
    union()
    {
        //edge ring
        difference()
        {
            rounded_square(sensor_width, sensor_width, sensor_thick, sensor_corner_radius);
            translate([0,(top_width-edge_width)/2,fudge/-2]) rounded_square(hole_x, hole_y, sensor_thick+fudge , sensor_corner_radius);
        }

        // toungue
        offset_from_bottom = u_height + u_y_offset + edge_width;
        translate([0,-1*(sensor_width - offset_from_bottom)/2, sensor_thick/2]) cube([tongue_width, sensor_width - offset_from_bottom, sensor_thick], center=true);

        // U Shape
        difference()
        {
            union()
            {
                translate([0,(edge_width)]) rounded_square(u_total_width, u_height, sensor_thick , sensor_corner_radius/2);
                translate([9,-edge_width,0]) cylinder(r=2.0, h=sensor_thick);
                translate([-9,-edge_width,0]) cylinder(r=2.0, h=sensor_thick);
            }
            // just harcode these holes
            translate([5.7,-edge_width,-0.5]) rounded_square(3, 16, sensor_thick+1 , 1);
            translate([-5.7,-(edge_width),-0.5]) rounded_square(3, 16, sensor_thick+1 , 1);
        }
    }

    difference()
    {
        hull()
        {

            translate([-9,-edge_width,0]) difference()
            {
                translate([0,0,-sensor_thick]) rounded_square(6, 7, sensor_thick , 2);
                translate([3.7,0,sensor_thick/-2]) cube([3, 7, sensor_thick+1] , center=true);
            }
            translate([8,-edge_width,0]) difference()
            {
                translate([0,0,-sensor_thick]) rounded_square(6, 7, sensor_thick , 2);
                translate([-2.5,0,sensor_thick/-2]) cube([3, 7, sensor_thick+1] , center=true);
            }
            translate([0,-edge_width,-2*sensor_thick]) rounded_square(7, 7, sensor_thick , 2);
        }
        translate([0,-edge_width,-0.5*sensor_thick]) cube([9,9,sensor_thick], center=true);
    }
    difference()
    {
        translate([0,-edge_width,-1.5*sensor_thick]) sphere(r=2, h=3);
        translate([0,-edge_width,-0.5*sensor_thick]) cube([9,9,sensor_thick], center=true);
    }
}

clip_thickness = 2.0; // wall thickness
clip_rise = 1.5; // thickness above clip
buffer = 0.25;  // space between sensor and clip

nub_height = 1.0; // thickness of nub that holds clip in
len_percentage = 0.27; // perctage of sensor length covered by clip
width_percentage = 0.85; // perctage of sensor width that's open

//base_radius=25.4;  //  2" diameter circle)
base_radius=23.8125;  // 1 7/8" diameter circle)
base_depth=3.175;   // 1/8"

union ()
{
    clip_outside = sensor_width+clip_thickness+buffer;
    clip_inside = sensor_width+buffer;

    translate([0,0,sensor_thick]) difference ()
    {
        cylinder(r=base_radius, h=base_depth);
        translate([0,(top_width-edge_width)/2,fudge/-2]) rounded_square(hole_x, hole_y, base_depth+fudge , sensor_corner_radius);
    }

    difference() {
        union()
        {
            difference()
            {
                translate([0,0,-clip_rise]) rounded_square(clip_outside, clip_outside, sensor_thick+clip_rise, sensor_corner_radius);
                translate([0,0,-clip_rise-fudge/2]) rounded_square(clip_inside, clip_inside, sensor_thick+clip_rise+fudge, sensor_corner_radius);
            }

            difference()
            {
                translate([0,0,-clip_rise-buffer]) rounded_square(clip_outside, clip_outside, clip_rise, sensor_corner_radius);
                translate([0,0,-clip_rise-buffer-fudge/2]) rounded_square(width_percentage*clip_outside, width_percentage*clip_outside, clip_rise+fudge, sensor_corner_radius);
            }
        }
        color([0.1,0.1,0.7]) translate([0,-0.5*(clip_outside*(1-len_percentage)+fudge),-nub_height]) cube([clip_outside+fudge,clip_outside*len_percentage+fudge,sensor_thick+clip_rise+fudge],center=true);
    }
}
