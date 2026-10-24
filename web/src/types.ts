export interface Vehicle {
  id: string;
  x: number;
  y: number;
  angle: number;
  speed: number;
  wait: number;
  origin: string;
  isEmergency?: boolean;
}

export interface TelemetryFrame {
  type: 'telemetry' | 'completed' | 'idle';
  step?: number;
  total_duration?: number;
  current_phase?: number;
  tls_state?: string;
  queues?: { [arm: string]: number };
  waiting_times?: { [arm: string]: number };
  counts?: { [arm: string]: number };
  total_queue?: number;
  total_active?: number;
  max_wait?: number;
  vehicles?: Vehicle[];
  summary?: SimulationSummary;
  manual_override_active?: boolean;
  manual_override_phase?: number | null;
  manual_override_remaining?: number;
}

export interface SimulationSummary {
  total_vehicles_departed: number;
  completed_vehicles: number;
  uncompleted_vehicles: number;
  completion_rate: number;
  throughput_per_minute: number;
  avg_trip_duration_sec: number;
  avg_waiting_time_sec: number;
  avg_waiting_time_all_sec: number;
  max_waiting_time_sec: number;
  avg_queue_length: number;
  max_queue_length: number;
  avg_stops_per_vehicle: number;
  wall_clock_time_sec: number;
  directional_performance: {
    [arm: string]: {
      completed: number;
      avg_duration: number;
      avg_waiting_time: number;
      avg_stops: number;
    };
  };
}

export interface BenchmarkRecord {
  scenario: string;
  controller: string;
  seed: number;
  avg_waiting_time_sec: number;
  avg_queue_length: number;
  throughput_per_minute: number;
  max_waiting_time_sec: number;
  completed_vehicles: number;
  total_vehicles: number;
  completion_rate: number;
}
