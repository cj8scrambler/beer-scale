import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { BeerglassComponent } from './beerglass.component';

describe('BeerglassComponent', () => {
  let component: BeerglassComponent;
  let fixture: ComponentFixture<BeerglassComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ BeerglassComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(BeerglassComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
