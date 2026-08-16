import type { ShipParticulars } from '@/types/api'

export interface StandardVesselType {
  id: string
  name: string
  category: string
  ship_type: string
  length_m: number
  beam_m: number
  draft_m: number
  cruising_speed_kn: number
  max_speed_kn: number
  fuelRating: 'Low Consumption' | 'High Economy' | 'Standard' | 'Heavy Displacement' | 'Ultra High'
  fuelLabel: string
  description: string
}

export const STANDARD_VESSEL_TYPES: StandardVesselType[] = [
  {
    id: 'ulcv',
    name: 'Ultra Large Container Vessel (ULCV / 24,000 TEU)',
    category: 'Container Carrier',
    ship_type: 'Container Ship (Golden-class)',
    length_m: 399.9,
    beam_m: 58.8,
    draft_m: 14.5,
    cruising_speed_kn: 19.5,
    max_speed_kn: 22.8,
    fuelRating: 'High Economy',
    fuelLabel: '140 MT / day (Eco-Steaming)',
    description: 'Long-haul intercontinental mega container carrier with bulbous bow hydrodynamics.',
  },
  {
    id: 'panamax_container',
    name: 'Panamax Container Ship (4,500 TEU)',
    category: 'Container Carrier',
    ship_type: 'Container Vessel (Panamax)',
    length_m: 294.0,
    beam_m: 32.2,
    draft_m: 12.0,
    cruising_speed_kn: 18.0,
    max_speed_kn: 21.5,
    fuelRating: 'Standard',
    fuelLabel: '65 MT / day',
    description: 'Standard workhorse container vessel for regional and feeder trade routes.',
  },
  {
    id: 'vlcc_tanker',
    name: 'VLCC Crude Oil Tanker (300,000 DWT)',
    category: 'Liquid Bulk / Tanker',
    ship_type: 'Crude Oil Tanker',
    length_m: 333.0,
    beam_m: 60.0,
    draft_m: 20.5,
    cruising_speed_kn: 14.5,
    max_speed_kn: 16.5,
    fuelRating: 'Heavy Displacement',
    fuelLabel: '75 MT / day (Heavy Draft)',
    description: 'Deep-draft crude carrier with heavy wave resistance and large turning radius.',
  },
  {
    id: 'capesize_bulk',
    name: 'Capesize Bulk Carrier (180,000 DWT)',
    category: 'Dry Bulk',
    ship_type: 'Bulk Carrier',
    length_m: 292.0,
    beam_m: 45.0,
    draft_m: 18.0,
    cruising_speed_kn: 14.0,
    max_speed_kn: 15.5,
    fuelRating: 'Standard',
    fuelLabel: '48 MT / day',
    description: 'Dry bulk carrier optimized for iron ore, coal, and bauxite transport.',
  },
  {
    id: 'lng_carrier',
    name: 'LNG Carrier (174,000 m³ Q-Flex)',
    category: 'Gas Carrier',
    ship_type: 'LNG Carrier',
    length_m: 299.0,
    beam_m: 46.4,
    draft_m: 12.0,
    cruising_speed_kn: 19.0,
    max_speed_kn: 21.0,
    fuelRating: 'High Economy',
    fuelLabel: 'Duel-Fuel Methane (Low Emission)',
    description: 'High-speed insulated gas carrier with minimal hull resistance.',
  },
  {
    id: 'mr2_tanker',
    name: 'Medium Range Product Tanker (MR2 / 50,000 DWT)',
    category: 'Liquid Bulk / Tanker',
    ship_type: 'Chemical/Oil Products Tanker',
    length_m: 183.0,
    beam_m: 32.2,
    draft_m: 11.2,
    cruising_speed_kn: 14.5,
    max_speed_kn: 16.0,
    fuelRating: 'Low Consumption',
    fuelLabel: '28 MT / day',
    description: 'Flexible coastal and short-sea refined petroleum and chemical transporter.',
  },
  {
    id: 'feeder_coaster',
    name: 'Coastal Feeder / General Cargo (10,000 DWT)',
    category: 'General Cargo',
    ship_type: 'General Cargo',
    length_m: 138.0,
    beam_m: 21.0,
    draft_m: 7.2,
    cruising_speed_kn: 13.0,
    max_speed_kn: 15.0,
    fuelRating: 'Low Consumption',
    fuelLabel: '14 MT / day',
    description: 'Shallow draft coastal vessel capable of navigating restricted waterways.',
  },
]

export function vesselToParticulars(vessel: StandardVesselType): ShipParticulars {
  return {
    ship_type: vessel.ship_type,
    length_m: vessel.length_m,
    beam_m: vessel.beam_m,
    draft_m: vessel.draft_m,
    cruising_speed_kn: vessel.cruising_speed_kn,
    max_speed_kn: vessel.max_speed_kn,
  }
}
