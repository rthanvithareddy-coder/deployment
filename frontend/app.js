const stateApi = "/api/state";
let currentState = null;
let ws = null;
const charts = {};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function chart(canvasId, config) {
  const canvas = $(canvasId);
  if (!canvas) return;
  if (charts[canvasId]) {
    charts[canvasId].data = config.data;
    charts[canvasId].options = config.options;
    charts[canvasId].update("none");
    return;
  }
  charts[canvasId] = new Chart(canvas, {
    ...config,
    options: {
      ...config.options,
      animation: false,
    },
  });
}

function baseChartOptions() {
  return {responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{boxWidth:10,font:{size:10}}}}, scales:{x:{grid:{display:false}}, y:{grid:{color:"#edf1f6"}}}};
}

function updateState(state) {
  currentState = state;
  const summary = state.summary;
  $("activeUsers").textContent = summary.active_users;
  $("availableTowers").textContent = summary.available_towers;
  $("totalHandovers").textContent = summary.total_handovers;
  $("averageSignal").textContent = `${summary.average_signal_dbm} dBm`;
  $("connectedUsers").textContent = summary.connected_users;
  $("successfulHandovers").textContent = summary.successful_handovers;
  $("failedHandovers").textContent = summary.failed_handovers;
  $("congestionStatus").textContent = summary.network_congestion;
  $("runStatus").textContent = state.running ? "Simulation Running" : "Simulation Paused";
  $("runStatus").parentElement.classList.toggle("running", state.running);

  const metrics = state.metrics;
  $("convSuccess").textContent = `${metrics.conventional.handover_success_rate}%`;
  $("mobSuccess").textContent = `${metrics.mobility.handover_success_rate}%`;
  $("avgDelay").textContent = `${Math.max(metrics.conventional.average_handover_delay_ms, metrics.mobility.average_handover_delay_ms)} ms`;
  $("avgThroughput").textContent = `${Math.max(metrics.conventional.average_throughput_mbps, metrics.mobility.average_throughput_mbps)} Mbps`;

  drawNetwork("networkCanvas");
  drawNetwork("simulationCanvas");
  updateActivity(state.events);
  updateTowerControls(state.towers);
  updateAlgorithmTable(state.users);
  updateCharts(state);
}

function drawNetwork(canvasId) {
  if (!currentState) return;
  const canvas = $(canvasId);
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = rect.width;
  const height = rect.height;
  const backingWidth = Math.round(width * dpr);
  const backingHeight = Math.round(height * dpr);
  if (canvas.width !== backingWidth || canvas.height !== backingHeight) {
    canvas.width = backingWidth;
    canvas.height = backingHeight;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--card").trim() || "#fff";
  ctx.fillRect(0,0,width,height);
  ctx.strokeStyle = "#edf1f6";
  ctx.lineWidth = 1;
  for(let x=40;x<width;x+=70){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,height);ctx.stroke();}
  for(let y=40;y<height;y+=70){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(width,y);ctx.stroke();}

  for (const tower of currentState.towers) {
    const x = tower.x / 100 * width;
    const y = tower.y / 100 * height;
    ctx.beginPath();ctx.arc(x,y,canvasId==="networkCanvas"?60:75,0,Math.PI*2);
    ctx.fillStyle=tower.enabled ? "rgba(36,107,253,.08)" : "rgba(239,68,68,.08)";
    ctx.fill();ctx.strokeStyle=tower.enabled?"rgba(36,107,253,.18)":"rgba(239,68,68,.28)";ctx.stroke();
    ctx.fillStyle=tower.enabled?"#246bfd":"#ef4444";ctx.beginPath();ctx.arc(x,y,11,0,Math.PI*2);ctx.fill();
    ctx.fillStyle="#fff";ctx.font="bold 9px Inter";ctx.textAlign="center";ctx.fillText(tower.id,x,y+3);
    ctx.fillStyle="#1f2b40";ctx.font="11px Inter";ctx.fillText(tower.name,x,y+27);
  }

  ctx.lineWidth=1;
  for (const user of currentState.users) {
    const x=user.x/100*width, y=user.y/100*height;
    const towerC=currentState.towers.find(t=>t.id===user.connected_conventional);
    if(towerC){
      ctx.strokeStyle="rgba(36,107,253,.24)";
      ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(towerC.x/100*width,towerC.y/100*height);ctx.stroke();
    }
    const towerM=currentState.towers.find(t=>t.id===user.connected_mobility);
    if(towerM){
      ctx.strokeStyle="rgba(32,182,220,.24)";
      ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(towerM.x/100*width,towerM.y/100*height);ctx.stroke();
    }
    const conventionalConnected = Boolean(user.connected_conventional);
    const mobilityConnected = Boolean(user.connected_mobility);
    ctx.fillStyle = !conventionalConnected && !mobilityConnected
      ? "#ef4444"
      : conventionalConnected && mobilityConnected
        ? "#7256d9"
        : conventionalConnected ? "#246bfd" : "#20b6dc";
    ctx.fillRect(x-4,y-7,8,14);
    ctx.fillStyle="#fff";ctx.fillRect(x-2,y-4,4,7);
  }
}

function updateActivity(events) {
  $("activityLog").innerHTML = events.length ? events.map(event =>
    `<div class="activity-item ${event.type==="failed"?"failed":"success"}">
      <strong>${event.type==="handover"?"Handover successful":event.type==="failed"?"Handover failed":"Network event"}</strong>
      <span>${event.user}: ${event.from||"none"} → ${event.to||"none"} · ${event.algorithm}</span>
      <div class="time">+${event.delay_ms} ms simulated delay</div>
    </div>`).join("") : '<div class="activity-item"><strong>No events yet</strong><span>Start the simulation to generate network events.</span></div>';
}

function updateTowerControls(towers) {
  $("towerControls").innerHTML=towers.map(tower =>
    `<div class="tower-row"><span><strong>${tower.name}</strong> · ${tower.conventional_load}/${tower.capacity}</span>
    <button onclick="toggleTower('${tower.id}',${!tower.enabled})">${tower.enabled?"Disable":"Enable"}</button></div>`).join("");
}

async function toggleTower(id, enabled) {
  await api(`/api/towers/${id}`,{method:"PATCH",body:JSON.stringify({enabled})});
  refreshState();
}

function updateAlgorithmTable(users) {
  $("algorithmTable").innerHTML=users.slice(0,30).map(user=>{
    const factors=Object.entries(user.factor_scores||{}).map(([id,values])=>`${id}:${values.score}`).join(" · ");
    return `<tr><td>${user.id}</td><td>${user.connected_conventional||"None"}</td><td>${user.signal_conventional}</td><td>${user.connected_mobility||"None"}</td><td>${user.signal_mobility}</td><td>${factors||"—"}</td></tr>`;
  }).join("") || '<tr><td colspan="6">No mobile users</td></tr>';
}

function updateCharts(state) {
  const c=state.metrics.conventional,m=state.metrics.mobility;
  chart("successMiniChart",{type:"bar",data:{labels:["Conventional","Mobility"],datasets:[{data:[c.handover_success_rate,m.handover_success_rate],backgroundColor:["#246bfd","#20b6dc"],borderRadius:5}]},options:{...baseChartOptions(),indexAxis:"y",plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,max:100},y:{grid:{display:false}}}}});
  chart("successChart",{type:"bar",data:{labels:["Conventional","Mobility-Aware"],datasets:[{label:"Success rate (%)",data:[c.handover_success_rate,m.handover_success_rate],backgroundColor:["#246bfd","#20b6dc"],borderRadius:6}]},options:{...baseChartOptions(),scales:{y:{beginAtZero:true,max:100}}}});
  const history=state.history.slice(-30);
  chart("signalChart",{type:"line",data:{labels:history.map((_,index)=>index+1),datasets:[
    {label:"Conventional",data:history.map(h=>h.signal_conventional),borderColor:"#246bfd",tension:.3,pointRadius:0},
    {label:"Mobility-Aware",data:history.map(h=>h.signal_mobility),borderColor:"#20b6dc",tension:.3,pointRadius:0}]},options:{...baseChartOptions(),scales:{y:{title:{display:true,text:"dBm"}}}}});
  chart("delayChart",{type:"bar",data:{labels:["Conventional","Mobility-Aware"],datasets:[{label:"Average delay (ms)",data:[c.average_handover_delay_ms,m.average_handover_delay_ms],backgroundColor:["#7256d9","#20b6dc"],borderRadius:6}]},options:{...baseChartOptions(),scales:{y:{beginAtZero:true}}}});
  chart("towerChart",{type:"bar",data:{labels:state.towers.map(t=>t.name),datasets:[
    {label:"Conventional utilization",data:state.towers.map(t=>t.conventional_load/t.capacity*100),backgroundColor:"#246bfd",borderRadius:5},
    {label:"Mobility utilization",data:state.towers.map(t=>t.mobility_load/t.capacity*100),backgroundColor:"#20b6dc",borderRadius:5}]},options:{...baseChartOptions(),scales:{y:{beginAtZero:true,max:100}}}});
}

async function refreshState(){updateState(await api(stateApi));}

const networkResizeFrames = new WeakMap();
const networkResizeObserver = new ResizeObserver(entries => {
  for (const entry of entries) {
    const canvas = entry.target;
    const frame = networkResizeFrames.get(canvas);
    if (frame) cancelAnimationFrame(frame);
    networkResizeFrames.set(canvas, requestAnimationFrame(() => {
      drawNetwork(canvas.id);
      networkResizeFrames.delete(canvas);
    }));
  }
});
for (const canvasId of ["networkCanvas", "simulationCanvas"]) {
  const canvas = $(canvasId);
  if (canvas) networkResizeObserver.observe(canvas);
}

document.querySelectorAll(".nav-item").forEach(button=>button.addEventListener("click",()=>{
  document.querySelectorAll(".nav-item").forEach(b=>b.classList.remove("active"));
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
  button.classList.add("active");
  $(button.dataset.page).classList.add("active");
  const titles={dashboard:["Network Overview","Real-time cellular mobility monitoring"],simulation:["Network Simulation","Configure and operate the virtual network"],algorithms:["Handover Algorithms","Compare handover decision engines"],analytics:["Performance Analytics","Calculated simulation performance"],scenarios:["Scenario Testing","Run predefined network conditions"],history:["Simulation History","Saved experiments and reports"],about:["About NetMotion","Project overview and methodology"]};
  $("pageTitle").textContent=titles[button.dataset.page][0];$("pageSubtitle").textContent=titles[button.dataset.page][1];
  document.querySelector(".sidebar").classList.remove("open");
  if(button.dataset.page==="history")loadHistory();
}));

$("menuButton").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
$("themeButton").addEventListener("click",()=>document.body.classList.toggle("dark"));
$("startBtn").addEventListener("click",()=>api("/api/simulations/start",{method:"POST"}).then(refreshState));
$("pauseBtn").addEventListener("click",()=>api("/api/simulations/pause",{method:"POST"}).then(refreshState));
$("resumeBtn").addEventListener("click",()=>api("/api/simulations/resume",{method:"POST"}).then(refreshState));
$("resetBtn").addEventListener("click",()=>api("/api/simulations/reset",{method:"POST"}).then(updateState));
$("applySettings").addEventListener("click",async()=>{
  await api("/api/settings",{method:"POST",body:JSON.stringify({user_count:+$("userCount").value,speed:+$("speed").value,handover_threshold:+$("threshold").value,stability_margin:+$("stability").value})});
  refreshState();
});
$("applyWeights").addEventListener("click",async()=>{
  await api("/api/settings",{method:"POST",body:JSON.stringify({weights:{signal:+$("weightSignal").value,capacity:+$("weightCapacity").value,mobility:+$("weightMobility").value}})});
  refreshState();
});
$("addUser").addEventListener("click",()=>api("/api/users",{method:"POST"}).then(updateState));
$("addTower").addEventListener("click",async()=>{
  const index=currentState.towers.length+1;
  await api("/api/towers",{method:"POST",body:JSON.stringify({id:`T${index}`,name:`Tower ${index}`,x:20+(index*17)%70,y:20+(index*13)%65,capacity:20,enabled:true})});
  refreshState();
});

document.querySelectorAll(".scenario-card").forEach(card=>card.querySelector("button").addEventListener("click",async()=>{
  await api(`/api/scenarios/${encodeURIComponent(card.dataset.scenario)}`,{method:"POST"});
  document.querySelector('[data-page="simulation"]').click();
  refreshState();
}));
$("saveExperiment").addEventListener("click",async()=>{
  const name=prompt("Experiment name","NetMotion Experiment");
  if(name){await api("/api/experiments",{method:"POST",body:JSON.stringify({name})});loadHistory();}
});
$("exportCsv").addEventListener("click",()=>window.open("/api/experiments/export/csv","_blank"));
$("exportPdf").addEventListener("click",()=>window.open("/api/experiments/export/pdf","_blank"));

async function loadHistory(){
  const records=await api("/api/experiments");
  $("historyTable").innerHTML=records.map(r=>`<tr><td>${r.id}</td><td>${r.name}</td><td>${new Date(r.created_at).toLocaleString()}</td><td>${r.duration_seconds}s</td><td>${r.user_count}</td><td>${r.tower_count}</td><td>${r.scenario}</td><td>${r.conventional_results.handover_success_rate}%</td><td>${r.mobility_results.handover_success_rate}%</td></tr>`).join("") || '<tr><td colspan="9">No experiments saved.</td></tr>';
}

function connectWebSocket(){
  const protocol=location.protocol==="https:"?"wss":"ws";
  ws=new WebSocket(`${protocol}://${location.host}/ws`);
  ws.onmessage=(event)=>{const message=JSON.parse(event.data);if(message.type==="state")updateState(message.state);};
  ws.onclose=()=>setTimeout(connectWebSocket,1500);
}

refreshState();
connectWebSocket();
