import { Component, Input } from '@angular/core';
import { Tap } from '../tap';

@Component({
  selector: 'app-tapstatus',
  templateUrl: './tapstatus.component.html',
  styleUrls: ['./tapstatus.component.css']
})
export class TapstatusComponent {

  @Input() tap: Tap;

}
