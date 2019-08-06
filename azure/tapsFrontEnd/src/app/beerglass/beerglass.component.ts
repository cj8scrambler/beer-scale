import { Component, Input, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { Tap } from '../tap';

@Component({
  selector: 'app-beerglass',
  templateUrl: './beerglass.component.html',
  styleUrls: ['./beerglass.component.css']
})

export class BeerglassComponent implements AfterViewInit {
  @Input() tap: Tap;
  @ViewChild('glass', { static: true }) public glass: ElementRef;

  public ngAfterViewInit() {
    const ctx: CanvasRenderingContext2D = (<HTMLCanvasElement>this.glass.nativeElement).getContext('2d');

    /* check for the needed properties */
    if (this.tap.hasOwnProperty('color') &&
      this.tap.hasOwnProperty('weight') &&
      this.tap.hasOwnProperty('tareempty') &&
      this.tap.hasOwnProperty('tarefull') &&
      this.tap.hasOwnProperty('style')) {
      var foam = 'normal'
      if ((this.tap.style == 'Cofee') || (this.tap.style == 'Cold Brew Coffee') ||
        (this.tap.style == 'Cider')) {
        foam = 'nofoam'
      }

      var percent = 100 * ((this.tap.weight - this.tap.tareempty) / (this.tap.tarefull - this.tap.tareempty));
      this.generateGlass(ctx, 10, 10, percent, this.tap.color, foam);

    } else {
      console.log("Invalid data")
    }
  }

  /* calculate the luman from any valid color specification */
  private color_to_luma(value) {
    var d = document.createElement("div");
    d.style.color = value;
    /* parse either rgb(r,g,b) or rgba(r,g,b,a) format */
    var colors = window.getComputedStyle(document.body.appendChild(d)).color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d+(?:\.\d+)?))?\)$/i);
    d.remove();
    
    if (colors) {
      return ((0.2126 * parseInt(colors[1])) + 
              (0.7152 * parseInt(colors[2])) + 
              (0.0722 * parseInt(colors[3]))); // SMPTE C, Rec. 709 weightings
    }
    else console.log("Unable to intepret '" + value + "' to luma");

  }

  /**
     * Draws a rounded & tapered rectangle.
     * @param {CanvasRenderingContext2D} ctx
     * @param {Number} x The top left x coordinate
     * @param {Number} y The top left y coordinate
     * @param {Number} width The width of the rectangle
     * @param {Number} height The height of the rectangle
     * @param {Number} [taper = 0] Taper on Y; it can also be an object to specify
                       different taper on bottom right & left
     * @param {Number} [taper.br = 0] Taper on Y; it can also be an object to specify
     * @param {Number} [taper.bl = 0] Taper on Y; it can also be an object to specify
     * @param {Number} [radius = 5] The corner radius; It can also be an object 
     *                 to specify different radii for corners
     * @param {Number} [radius.tl = 0] Top left
     * @param {Number} [radius.tr = 0] Top right
     * @param {Number} [radius.br = 0] Bottom right
     * @param {Number} [radius.bl = 0] Bottom left
     * @param {Boolean} [fill = false] Whether to fill the rectangle.
     * @param {Boolean} [stroke = true] Whether to stroke the rectangle.
     */
  roundTaperRect(ctx, x, y, width, height, taper, radius, fill, stroke) {
    if (typeof stroke == 'undefined') {
      stroke = true;
    }
    if (typeof radius === 'undefined') {
      radius = 5;
    }
    if (typeof radius === 'number') {
      radius = { tl: radius, tr: radius, br: radius, bl: radius };
    } else {
      var defaultRadius = { tl: 0, tr: 0, br: 0, bl: 0 };
      for (var side in defaultRadius) {
        radius[side] = radius[side] || defaultRadius[side];
      }
    }
    if (typeof taper === 'undefined') {
      taper = 0;
    }
    if (typeof taper === 'number') {
      taper = { br: taper, bl: taper };
    } else {
      var defaultTaper = { tl: 0, tr: 0, br: 0, bl: 0 };
      for (var side in defaultTaper) {
        taper[side] = taper[side] || defaultTaper[side];
      }
    }
    ctx.beginPath();
    ctx.moveTo(x + radius.tl, y);
    ctx.lineTo(x + width - radius.tr, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius.tr);
    ctx.lineTo(x + width - taper.br, y + height - radius.br);
    ctx.quadraticCurveTo(x + width - taper.br, y + height, x + width - taper.br - radius.br, y + height);
    ctx.lineTo(x + taper.bl + radius.bl, y + height);
    ctx.quadraticCurveTo(x + taper.bl, y + height, x + taper.bl, y + height - radius.bl);
    ctx.lineTo(x, y + radius.tl);
    ctx.quadraticCurveTo(x, y, x + radius.tl, y);
    ctx.closePath();
    if (fill) {
      ctx.fill();
    }
    if (stroke) {
      ctx.stroke();
    }
  }

  generateGlass(canvas, x, y, percent = 100, color = "20", mode = "normal") {
    //console.log("generateGlass(", percent, ",", color, "," + mode + ")");

    //mode : [normal | nofoam | blank]]

    var w = 140       // glass width
    var h = 240       // glass height
    var th = 10       // glass thickness
    var ta = 18       // taper
    var foam = 45     // foam height
    var buffer = h * 0.05  // vertical buffer

    var glass_color = "rgba(255, 255, 255, 0.17)";
    var foam_color = "rgba(255, 255, 220, 0.65)";
    var shine_color = "rgba(255, 255, 255, .18)";
    var text_color = "rgba(255, 255, 255, 0.8)";

    var glassradius = { tl: 0, tr: 0, bl: 0, br: 0 };
    glassradius.tl = 2
    glassradius.tr = 2
    glassradius.bl = 16
    glassradius.br = 16

    var beerradius = { tl: 0, tr: 0, bl: 0, br: 0 };
    beerradius.tl = 0
    beerradius.tr = 0
    beerradius.bl = 30
    beerradius.br = 30

    /* SRM -> RGB */
    var srm2rgb = {}
    srm2rgb[1] = "#FFE699"
    srm2rgb[2] = "#FFD878"
    srm2rgb[3] = "#FFCA5A"
    srm2rgb[4] = "#FFBF42"
    srm2rgb[5] = "#FBB123"
    srm2rgb[6] = "#F8A600"
    srm2rgb[7] = "#F39C00"
    srm2rgb[8] = "#EA8F00"
    srm2rgb[9] = "#E58500"
    srm2rgb[10] = "#DE7C00"
    srm2rgb[11] = "#C17A37"
    srm2rgb[12] = "#BF7138"
    srm2rgb[13] = "#BC6733"
    srm2rgb[14] = "#B26033"
    srm2rgb[15] = "#A85839"
    srm2rgb[16] = "#985336"
    srm2rgb[17] = "#8D4C32"
    srm2rgb[18] = "#7C452D"
    srm2rgb[19] = "#6B3A1E"
    srm2rgb[20] = "#5D341A"
    srm2rgb[21] = "#4E2A0C"
    srm2rgb[22] = "#402C27"
    srm2rgb[23] = "#361F1B"
    srm2rgb[24] = "#261716"
    srm2rgb[25] = "#231716"
    srm2rgb[26] = "#19100F"
    srm2rgb[27] = "#16100F"
    srm2rgb[28] = "#120D0C"
    srm2rgb[29] = "#100B0A"
    srm2rgb[30] = "#050B0A"
    srm2rgb[31] = "#000000"

    // 'percent' is the number shown
    if (percent < 0)
      percent = 0
    else if (percent > 100)
      percent = 100

    // 'draw_percent' is the amount the glass is filled
    var draw_percent = percent
    if ((percent > 0) && (percent < 20))
      draw_percent = 20

    // if color was 0-50, assume it's SRM
    var srm = parseInt(color, 10)
    if (srm >= 0 && srm <= 50) {
      if (srm < 1)
        srm = 1
      else if (srm > 31)
        srm = 31

      color = srm2rgb[srm]
    }

    /* figure out what text will look good on top of beer */
    if (draw_percent > 0) {
      var luma = this.color_to_luma(color)
      if (luma <= 64)
        text_color = "rgba(210, 210, 210, 0.7)";
      else if (luma <= 128)
        text_color = "rgba(255, 255, 255, 0.7)";
      else if (luma <= 192)
        text_color = "rgba(0, 0, 0, 0.7)";
      else
        text_color = "rgba(30, 30, 30, 0.7)";
    }
    if (mode == "nofoam")
      foam_color = color

    /* Might be redrawing, so clear it first */
    canvas.clearRect(x, y - buffer / 2, w, h + buffer / 2);

    // Glass
    canvas.beginPath();
    this.roundTaperRect(canvas, x, y - buffer / 2, w, h + buffer, ta, glassradius, false, false);
    canvas.fillStyle = glass_color;
    canvas.fill();

    if ((mode != "blank") && (draw_percent > 0)) {
      // Beer
      var beer_taper = ta * (draw_percent / 100.0)
      var beer_x = x + th + (ta - beer_taper)
      var beer_y = y + (1 - (draw_percent / 100.0)) * h + th
      var beer_w = w - 2 * (ta - beer_taper) - 2 * th;
      var beer_h = h * (draw_percent / 100.0) - 2 * th;
      canvas.beginPath();
      this.roundTaperRect(canvas, beer_x, beer_y, beer_w, beer_h, beer_taper, beerradius, false, false);
      canvas.fillStyle = color;
      canvas.fill();

      // Foam
      var foam_height = (draw_percent / 100.0) * foam
      var foam_x = beer_x
      var foam_y = beer_y
      var foam_w = beer_w
      var foam_h = foam * (draw_percent / 100.0);
      var foam_ratio = (foam_h) / (beer_h)
      var foam_taper = ta * foam_ratio;
      canvas.beginPath();
      this.roundTaperRect(canvas, foam_x, foam_y, foam_w, foam_h, foam_taper, 0, false, false);
      canvas.fillStyle = foam_color;
      canvas.fill();
    }

    // Shine right
    var shinerradius = { tl: 0, tr: 0, bl: 0, br: 0 };
    shinerradius.tl = 0.5 * glassradius.tl
    shinerradius.tr = 0.5 * glassradius.tr
    shinerradius.bl = 0.5 * glassradius.bl
    shinerradius.br = glassradius.br
    var shinertaper = { bl: 0, br: 0 };
    shinertaper.bl = 0
    shinertaper.br = ta
    canvas.beginPath();
    this.roundTaperRect(canvas, x + w / 2, y, (w - th) / 2, h, shinertaper, shinerradius, false, false);
    canvas.fillStyle = shine_color;
    canvas.fill();

    // Shine left
    var shine_x = x + 0.15 * w   /* start 15% right */
    var shine_y = y + 0.09 * h   /* start 9% down */
    var shine_w = w * 0.1        /* 10% wide */
    var shine_h = h * 0.85       /* 85% high */
    var shinelradius = { tl: 0, tr: 0, bl: 0, br: 0 };
    shinelradius.tl = 5 * glassradius.tl
    shinelradius.tr = 2 * glassradius.tr
    shinelradius.bl = 0
    shinelradius.br = 0
    var shineltaper = { bl: 0, br: 0 };
    shineltaper.bl = 0.8 * ta
    shineltaper.br = 0
    canvas.beginPath();
    this.roundTaperRect(canvas, shine_x, shine_y, shine_w, shine_h, shineltaper, shinelradius, false, false);
    canvas.fillStyle = shine_color;
    canvas.fill();

    // Percentage
    if (mode != "blank") {
      canvas.font = "32px Quicksand";
      canvas.textAlign = "center";
      canvas.fillStyle = text_color;
      canvas.fillText(Math.round(percent) + "%", x + w / 2, y + .85 * h);
    }
  }
}
