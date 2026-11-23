import React from "react";
import { Button, Input } from "@flatmate/ui";
import { Bed, Plus, Trash2 } from "lucide-react";
import { newBed, newRoom, type DraftBed, type DraftRoom } from "../draft";
import { CheckboxField, SelectField, type StepProps } from "./fields";

/** Immutable helpers: the old wizard edited room objects in place. */
function useRooms({ draft, update }: StepProps) {
  const setRooms = (rooms: DraftRoom[]) => update({ rooms });
  const patchRoom = (id: string, patch: Partial<DraftRoom>) => setRooms(draft.rooms.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const patchBed = (roomId: string, bedId: string, patch: Partial<DraftBed>) =>
    setRooms(draft.rooms.map((r) => (r.id === roomId ? { ...r, beds: r.beds.map((b) => (b.id === bedId ? { ...b, ...patch } : b)) } : r)));
  return { setRooms, patchRoom, patchBed };
}

export function RoomsStep(props: StepProps) {
  const { draft } = props;
  const { setRooms, patchRoom } = useRooms(props);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-charcoal-muted">Add each bedroom you&apos;re renting out.</p>
        <Button size="sm" variant="outline" className="gap-1.5 shrink-0" onClick={() => setRooms([...draft.rooms, newRoom(draft.rooms.length + 1)])}>
          <Plus className="w-3.5 h-3.5" />
          <span>Add room</span>
        </Button>
      </div>

      {draft.rooms.map((room, idx) => (
        <fieldset key={room.id} className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
          <div className="flex items-center justify-between">
            <legend className="font-bold text-sm text-charcoal">Room {idx + 1}</legend>
            {draft.rooms.length > 1 && (
              <button
                type="button"
                onClick={() => setRooms(draft.rooms.filter((r) => r.id !== room.id))}
                className="inline-flex items-center gap-1 min-h-[44px] px-2 text-rose-600 hover:text-rose-700 text-xs"
              >
                <Trash2 className="w-3.5 h-3.5" /> Remove
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Name" value={room.name} onChange={(e) => patchRoom(room.id, { name: e.target.value })} />
            <SelectField
              id={`room-type-${room.id}`}
              label="Type"
              value={room.type}
              onChange={(type) => patchRoom(room.id, { type: type as DraftRoom["type"] })}
              options={[
                { value: "private", label: "Private room" },
                { value: "shared", label: "Shared room" },
              ]}
            />
            <Input label="Rent (₹/month)" type="number" inputMode="numeric" min={1} value={room.rent} onChange={(e) => patchRoom(room.id, { rent: e.target.value })} />
            <Input label="Deposit (₹, optional)" type="number" inputMode="numeric" min={0} value={room.deposit} onChange={(e) => patchRoom(room.id, { deposit: e.target.value })} />
          </div>
          <CheckboxField
            id={`room-bath-${room.id}`}
            label="Private attached bathroom"
            checked={room.privateBath}
            onChange={(privateBath) => patchRoom(room.id, { privateBath })}
          />
        </fieldset>
      ))}
    </div>
  );
}

export function BedsStep(props: StepProps) {
  const { draft } = props;
  const { patchRoom, patchBed } = useRooms(props);
  return (
    <div className="space-y-4">
      <p className="text-xs text-charcoal-muted">
        Each bed can be rented on its own. Leave a bed&apos;s rent blank to split the room rent evenly.
      </p>
      {draft.rooms.map((room) => (
        <section key={room.id} className="p-4 border border-slate-200 rounded-2xl space-y-3 bg-white">
          <div className="flex items-center justify-between gap-2">
            <h3 className="flex items-center gap-2 font-bold text-sm text-charcoal min-w-0">
              <Bed className="w-4 h-4 text-forest shrink-0" />
              <span className="truncate">{room.name || "Unnamed room"}</span>
            </h3>
            <Button
              size="sm"
              variant="ghost"
              className="shrink-0"
              onClick={() => patchRoom(room.id, { beds: [...room.beds, newBed(`Bed ${String.fromCharCode(65 + room.beds.length)}`)] })}
            >
              + Add bed
            </Button>
          </div>
          <ul className="space-y-2">
            {room.beds.map((bed) => (
              <li key={bed.id} className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl grid grid-cols-1 min-[480px]:grid-cols-[1fr_1fr_auto] gap-2 items-end">
                <Input label="Bed" value={bed.identifier} onChange={(e) => patchBed(room.id, bed.id, { identifier: e.target.value })} />
                <Input
                  label="Rent (₹/month)"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  placeholder="Split evenly"
                  value={bed.rent}
                  onChange={(e) => patchBed(room.id, bed.id, { rent: e.target.value })}
                />
                <div className="flex items-center gap-2">
                  <CheckboxField
                    id={`bed-occupied-${bed.id}`}
                    label="Occupied"
                    checked={bed.occupied}
                    onChange={(occupied) => patchBed(room.id, bed.id, { occupied })}
                  />
                  {room.beds.length > 1 && (
                    <button
                      type="button"
                      aria-label={`Remove ${bed.identifier}`}
                      onClick={() => patchRoom(room.id, { beds: room.beds.filter((b) => b.id !== bed.id) })}
                      className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-rose-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
