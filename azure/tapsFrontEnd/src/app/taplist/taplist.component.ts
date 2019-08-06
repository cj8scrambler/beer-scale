import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable} from 'rxjs';

import { Tap } from '../tap';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-taplist',
  templateUrl: './taplist.component.html',
  styleUrls: ['./taplist.component.css']
})

export class TaplistComponent implements OnInit {

  tapList$: Observable<Tap[]>;
  isloading;

  constructor(private httpClient: HttpClient) {
    this.get_taplist();
  }

  ngOnInit() {
    this.isloading = true;
  }

  get_taplist() {
    this.httpClient.get(environment.apiUrl + '/').subscribe((res: Observable<Tap[]>) => {
      this.tapList$ = res;
      this.isloading = false;
    });
  }
}
