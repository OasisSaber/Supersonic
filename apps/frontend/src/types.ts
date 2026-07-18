export type RiskLevel = 'low' | 'medium' | 'high'

export interface VehicleState {
  speed: number
  gear: string
  battery: number
  range_km: number
  drive_mode: string
  battery_temperature: number
  seatbelt_fastened: boolean
}

export interface RoadState {
  pedestrian_detected: boolean
  vehicle_count: number
  lane_departure: boolean
  front_vehicle_risk: RiskLevel
}

export interface DriverState {
  fatigue_level: RiskLevel
  distracted: boolean
  eyes_closed_duration: number
  yawning: boolean
}

export interface RiskEvent {
  event: string
  level: RiskLevel
  timestamp: number
  message: string
  evidence: string[]
}

export interface SimulationFrame {
  sequence: number
  vehicle: VehicleState
  sensor: {
    timestamp: number
    road: RoadState
    driver: DriverState
    vehicle: VehicleState
  }
  risk: RiskEvent
}

export interface TripRecord {
  trip_id: string
  duration_seconds: number
  frames_processed: number
  highest_risk: RiskLevel
  events: RiskEvent[]
  summary: string
}

