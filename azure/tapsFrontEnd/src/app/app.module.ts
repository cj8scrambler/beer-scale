import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule } from '@angular/common/http';
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AppComponent } from './app.component';
import { TaplistComponent } from './taplist/taplist.component';
import { ConfiglistComponent } from './configlist/configlist.component';
import { TapstatusComponent } from './tapstatus/tapstatus.component';
import { BeerglassComponent } from './beerglass/beerglass.component';

const appRoutes: Routes = [
  { path: 'taplist', component: TaplistComponent },
  { path: 'config',  component: ConfiglistComponent },
  { path: '',
    redirectTo: '/taplist',
    pathMatch: 'full'
  }
  //{ path: '**', component: PageNotFoundComponent }
];

@NgModule({
  declarations: [
    AppComponent,
    TaplistComponent,
    ConfiglistComponent,
    TapstatusComponent,
    BeerglassComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    RouterModule.forRoot(
      appRoutes,
      //{ enableTracing: true } // <-- debugging purposes only
    )  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
