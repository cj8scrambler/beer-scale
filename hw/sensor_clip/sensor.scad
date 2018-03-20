// Fine detail
//$fa = 0.5;
//$fs = 0.5;

// Coarse detail
$fa = 1.0;
$fs = 1.5;

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

color([0.7,0.7,0.7])union()
{
    //edge ring
    difference()
    {
        rounded_square(sensor_width, sensor_width, sensor_thick, sensor_corner_radius);
    
        hole_x = sensor_width - 2 * edge_width;
        hole_y = sensor_width - edge_width - top_width;
        fudge_z = 1; // used to make subtractive area a little thicker
    
        translate([0,(top_width-edge_width)/2,fudge_z/-2]) rounded_square(hole_x, hole_y, sensor_thick+fudge_z , sensor_corner_radius);
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

color([0.7,0.7,0.7]) union()
{
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
