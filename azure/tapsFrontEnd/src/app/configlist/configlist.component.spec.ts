import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { ConfiglistComponent } from './configlist.component';

describe('ConfiglistComponent', () => {
  let component: ConfiglistComponent;
  let fixture: ComponentFixture<ConfiglistComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ ConfiglistComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(ConfiglistComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
