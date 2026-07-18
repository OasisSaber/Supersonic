const stateData = {
  stable: {
    label: 'STABLE / 稳定',
    message: '当前通勤状态稳定',
    action: '道路与驾驶状态无显著风险',
    time: '00:24.8',
    timestamp: '24.8 s',
    speed: '48',
    vehicleCount: 'VEHICLE · 2',
    lane: '保持稳定',
    frontRisk: '低',
    gaze: '正常',
    fatigue: '低',
    eyes: '0.1s',
    pedestrian: false,
    evidence: ['车道状态稳定', '驾驶员视线正常'],
    assistant: '当前没有需要解释的显著风险事件。',
    timeline: [],
  },
  attention: {
    label: 'ATTENTION / 注意',
    message: '注意前车距离变化',
    action: '保持观察，减少非必要操作',
    time: '00:40.0',
    timestamp: '40.0 s',
    speed: '42',
    vehicleCount: 'VEHICLE · 4',
    lane: '保持稳定',
    frontRisk: '中',
    gaze: '正常',
    fatigue: '低',
    eyes: '0.2s',
    pedestrian: false,
    evidence: ['前车风险：中', '车辆数量：4'],
    assistant: '结构化事件显示前车风险升至中等级，当前未检测到驾驶员分心。',
    timeline: [
      { title: '注意前车距离变化', detail: '40.0秒 · 中风险 · 前车风险：中' },
    ],
  },
  critical: {
    label: 'CRITICAL / 高风险',
    message: '前方行人，注意力偏移',
    action: '请立即关注前方',
    time: '02:05.6',
    timestamp: '125.6 s',
    speed: '32',
    vehicleCount: 'VEHICLE · 3',
    lane: '保持稳定',
    frontRisk: '中',
    gaze: '偏移',
    fatigue: '中',
    eyes: '0.4s',
    pedestrian: true,
    evidence: ['前方检测到行人', '驾驶员注意力偏移'],
    assistant: '125.6秒检测到前方行人，同时驾驶员注意力偏移，因此规则引擎生成复合高风险事件。',
    timeline: [
      { title: '前方行人，注意力偏移', detail: '125.6秒 · 高风险 · 复合事件' },
      { title: '车道偏离趋势与疲劳', detail: '82.0秒 · 中风险 · Mock事件' },
      { title: '注意前车距离变化', detail: '40.0秒 · 中风险 · Mock事件' },
    ],
  },
}

const shell = document.querySelector('#hmiShell')
const stateButtons = [...document.querySelectorAll('.state-button')]
const themeButtons = [...document.querySelectorAll('.theme-button')]
const specToggle = document.querySelector('#specToggle')
const explainButton = document.querySelector('#explainButton')
const reportButton = document.querySelector('#reportButton')
const roadVideo = document.querySelector('#roadVideo')

let currentState = 'stable'

function setText(id, value) {
  const element = document.querySelector(`#${id}`)
  if (element) element.textContent = value
}

function renderTimeline(events) {
  const list = document.querySelector('#timelineList')
  if (!events.length) {
    list.innerHTML = '<li class="empty-event"><span class="event-dot"></span><div><strong>等待风险事件</strong><small>稳定状态不写入风险时间线</small></div></li>'
    return
  }

  list.innerHTML = events
    .map((event) => `<li><span class="event-dot"></span><div><strong>${event.title}</strong><small>${event.detail}</small></div></li>`)
    .join('')
}

function renderEvidence(items) {
  const list = document.querySelector('#evidenceList')
  list.replaceChildren(...items.map((item) => {
    const node = document.createElement('li')
    node.textContent = item
    return node
  }))
}

function syncRoadVideo(timestamp) {
  if (!roadVideo || !Number.isFinite(roadVideo.duration)) return

  const seconds = Number.parseFloat(timestamp)
  if (Number.isFinite(seconds)) {
    roadVideo.currentTime = seconds % roadVideo.duration
  }

  roadVideo.play().catch(() => {
    setText('roadSourceStatus', 'CC0 城市行车素材 · 点击页面后播放')
  })
}

function applyState(state) {
  const data = stateData[state]
  currentState = state
  shell.dataset.state = state

  stateButtons.forEach((button) => {
    button.classList.remove('is-active')
    button.setAttribute('aria-pressed', 'false')
  })
  const activeButton = stateButtons.find((button) => button.dataset.state === state)
  activeButton?.classList.add('is-active')
  activeButton?.setAttribute('aria-pressed', 'true')

  setText('riskLabel', data.label)
  setText('riskMessage', data.message)
  setText('riskAction', data.action)
  setText('eventTime', data.time)
  setText('roadTimestamp', data.timestamp)
  setText('speedValue', data.speed)
  setText('laneState', data.lane)
  setText('frontRisk', data.frontRisk)
  setText('gazeState', data.gaze)
  setText('fatigueState', data.fatigue)
  setText('eyesState', data.eyes)
  setText('assistantText', data.assistant)
  syncRoadVideo(data.timestamp)

  const vehicleTarget = document.querySelector('#vehicleTarget span')
  vehicleTarget.textContent = data.vehicleCount
  document.querySelector('#pedestrianTarget').hidden = !data.pedestrian

  renderEvidence(data.evidence)
  renderTimeline(data.timeline)

  reportButton.disabled = state === 'critical'
  reportButton.title = state === 'critical' ? '高风险状态下暂不开放长报告' : ''
}

stateButtons.forEach((button) => {
  button.addEventListener('click', () => applyState(button.dataset.state))
})

themeButtons.forEach((button) => {
  button.addEventListener('click', () => {
    shell.dataset.theme = button.dataset.theme
    themeButtons.forEach((item) => {
      const active = item === button
      item.classList.toggle('is-active', active)
      item.setAttribute('aria-pressed', String(active))
    })
  })
})

specToggle.addEventListener('click', () => {
  const enabled = shell.classList.toggle('spec-mode')
  specToggle.setAttribute('aria-pressed', String(enabled))
  specToggle.textContent = enabled ? '关闭标注' : '规范标注'
})

explainButton.addEventListener('click', () => {
  setText('assistantText', stateData[currentState].assistant)
})

reportButton.addEventListener('click', () => {
  setText('assistantText', currentState === 'stable'
    ? '本次Mock通勤尚无显著风险事件，可在行程结束后生成完整结构化摘要。'
    : '行程报告会汇总事件时间点、风险等级和证据；驾驶中不展示长报告。')
})

if (roadVideo) {
  roadVideo.addEventListener('loadeddata', () => {
    shell.classList.add('video-ready')
    setText('roadSourceStatus', 'CC0 城市行车素材 · Mock 感知叠加')
    syncRoadVideo(stateData[currentState].timestamp)
  })

  roadVideo.addEventListener('error', () => {
    shell.classList.remove('video-ready')
    setText('roadSourceStatus', '视频未载入 · 已切换 Mock 降级画面')
  })
}

const params = new URLSearchParams(window.location.search)
const requestedState = params.get('state')
const requestedTheme = params.get('theme')
const initialState = Object.hasOwn(stateData, requestedState) ? requestedState : 'stable'

if (requestedTheme === 'day' || requestedTheme === 'night') {
  shell.dataset.theme = requestedTheme
  themeButtons.forEach((button) => {
    const active = button.dataset.theme === requestedTheme
    button.classList.toggle('is-active', active)
    button.setAttribute('aria-pressed', String(active))
  })
}

if (params.get('spec') === '1') {
  shell.classList.add('spec-mode')
  specToggle.setAttribute('aria-pressed', 'true')
  specToggle.textContent = '关闭标注'
}

applyState(initialState)
