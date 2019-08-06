export class Datapoint {
  deviceid: string;
  scale: number;
  timestamp: number;
  weight: number;
  temperature: number;
}

export class Tap {
  deviceid: string;
  scale: number;
  tapname: string;
  beername: string;
  brewer: string;
  style: string;
  location: string;
  abv: number;
  color: string;
  ibu: number;
  temperature: number;
  weight: number;
  tarefull: number;
  tareempty: number;
  history: Datapoint[];
}