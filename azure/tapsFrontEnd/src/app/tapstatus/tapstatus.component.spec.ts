import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { TapstatusComponent } from './tapstatus.component';

describe('TapstatusComponent', () => {
  let component: TapstatusComponent;
  let fixture: ComponentFixture<TapstatusComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ TapstatusComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(TapstatusComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
