// A small Standard MIDI File reader and synth. The downloadable .mid is the score.
export function parseMidi(buffer) {
  const data = new DataView(buffer); let offset=0;
  const str = n => {let s='';while(n--)s+=String.fromCharCode(data.getUint8(offset++));return s;};
  const u16 = () => {const x=data.getUint16(offset);offset+=2;return x;};
  const u32 = () => {const x=data.getUint32(offset);offset+=4;return x;};
  const variable = () => {let value=0, b;do {b=data.getUint8(offset++);value=(value<<7)|(b&127);}while(b&128);return value;};
  if(str(4)!=='MThd')throw Error('Invalid MIDI header');
  const header=u32();u16();const tracks=u16(), division=u16();offset+=header-6;
  if(division&0x8000)throw Error('SMPTE MIDI is unsupported');
  const events=[];
  for(let t=0;t<tracks;t++){
    if(str(4)!=='MTrk')throw Error('Invalid MIDI track');
    const length=u32(),end=offset+length;let tick=0,running=0;
    while(offset<end){
      tick+=variable();let status=data.getUint8(offset++);
      if(status<128){offset--;status=running;}else if(status<240)running=status;
      if(status===255){const type=data.getUint8(offset++),n=variable();if(type===81)events.push({tick,type:'tempo',value:(data.getUint8(offset)<<16)|(data.getUint8(offset+1)<<8)|data.getUint8(offset+2)});if(type===47)events.push({tick,type:'marker'});offset+=n;continue;}
      if(status===240||status===247){offset+=variable();continue;}
      const kind=status>>4,channel=status&15,a=data.getUint8(offset++),b=kind===12||kind===13?0:data.getUint8(offset++);
      if(kind===9||kind===8)events.push({tick,type:kind===8||b===0?'off':'on',channel,note:a,velocity:b});
      if(kind===12)events.push({tick,type:'program',channel,program:a});
    }
  }
  events.sort((a,b)=>a.tick-b.tick);let tick=0,seconds=0,tempo=500000;const active=new Map(),notes=[],programs={};
  for(const event of events){seconds+=(event.tick-tick)*tempo/1000000/division;tick=event.tick;
    if(event.type==='tempo'){tempo=event.value;continue;}
    if(event.type==='program'){programs[event.channel]=event.program;continue;}
    const key=event.channel+':'+event.note;
    if(event.type==='on')active.set(key,{...event,time:seconds,program:programs[event.channel]||0});
    if(event.type==='off'&&active.has(key)){const onset=active.get(key);notes.push({...onset,duration:seconds-onset.time});active.delete(key);}
  }
  notes.sort((a,b)=>a.time-b.time);
  return {notes,duration:Math.ceil(seconds*1000)/1000};
}

export class MidiMusic {
  constructor(){this.playing=false;this.voices=new Set();this.timer=null;}
  async start(){
    if(this.playing)return;
    if(!this.context){
      const Audio=window.AudioContext||window.webkitAudioContext;
      if(!Audio)throw Error('Audio is unavailable in this browser');
      this.context=new Audio();this.master=this.context.createGain();this.master.gain.value=.2;
      const filter=this.context.createBiquadFilter();filter.type='lowpass';filter.frequency.value=2900;
      const delay=this.context.createDelay(2);delay.delayTime.value=.34;const feedback=this.context.createGain();feedback.gain.value=.31;
      this.master.connect(filter);filter.connect(this.context.destination);filter.connect(delay);delay.connect(feedback);feedback.connect(delay);delay.connect(this.context.destination);
    }
    // Resume within the explicit user gesture, before awaiting the file.
    await this.context.resume();
    if(!this.score){const response=await fetch('commons.mid');if(!response.ok)throw Error('MIDI score unavailable');this.score=parseMidi(await response.arrayBuffer());}
    this.playing=true;this.startTime=this.context.currentTime+.08;this.index=0;this.loop=0;
    this.schedule();this.timer=setInterval(()=>this.schedule(),100);
  }
  schedule(){
    if(!this.playing)return;
    const now=this.context.currentTime;
    while(this.startTime+this.loop*this.score.duration+this.score.notes[this.index].time<now+1.5){
      const note=this.score.notes[this.index],time=this.startTime+this.loop*this.score.duration+note.time;
      if(time>=now-.05)this.voice(note,Math.max(time,now));
      this.index++;if(this.index===this.score.notes.length){this.index=0;this.loop++;}
    }
  }
  voice(note,time){
    const oscillator=this.context.createOscillator(),gain=this.context.createGain(),pan=this.context.createStereoPanner();
    oscillator.type=note.channel===1?'sine':note.channel===2?'triangle':'sine';
    oscillator.frequency.value=440*Math.pow(2,(note.note-69)/12);
    oscillator.detune.value=note.channel===0?(note.note%3-1)*5:0;
    pan.pan.value=note.channel===1?(note.note%5-2)*.22:0;
    const level=(note.velocity/127)*(note.channel===0?.15:note.channel===1?.35:.5);
    gain.gain.setValueAtTime(0,time);gain.gain.linearRampToValueAtTime(level,time+(note.channel===0?.35:.025));
    gain.gain.exponentialRampToValueAtTime(.0001,time+note.duration+.5);
    oscillator.connect(gain);gain.connect(pan);pan.connect(this.master);
    oscillator.start(time);oscillator.stop(time+note.duration+.55);this.voices.add(oscillator);
    oscillator.onended=()=>{this.voices.delete(oscillator);oscillator.disconnect();gain.disconnect();pan.disconnect();};
  }
  stop(){this.playing=false;clearInterval(this.timer);for(const voice of this.voices){try{voice.stop();}catch{}}this.voices.clear();if(this.context)this.context.suspend();}
  async toggle(){if(this.playing)this.stop();else await this.start();return this.playing;}
}
