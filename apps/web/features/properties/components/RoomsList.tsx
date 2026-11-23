import React from "react";
import type { PropertyDTO } from "@flatmate/contracts";
import { Button } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";

type Room = NonNullable<PropertyDTO["rooms"]>[number];

interface RoomsListProps {
  rooms: Room[];
  currency: string;
  onApply: (room: Room) => void;
}

export function RoomsList({ rooms, currency, onApply }: RoomsListProps) {
  if (rooms.length === 0) return null;
  return (
    <section>
      <h2 className="text-lg font-bold text-charcoal mb-3">Rooms in this flat</h2>
      <div className="space-y-3">
        {rooms.map((room) => {
          const occupied = room.beds?.filter((b) => b.is_occupied).length ?? 0;
          return (
            <div key={room.id} className="p-4 bg-white rounded-2xl border border-warm-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
              <div className="min-w-0">
                <h3 className="font-bold text-charcoal text-sm">{room.room_name}</h3>
                <p className="text-xs text-charcoal-muted mt-0.5">
                  {room.private_bath ? "Private bathroom" : "Shared bathroom"}
                  {room.available_from ? ` • Available from ${formatDate(room.available_from)}` : ""}
                </p>
                {room.beds && room.beds.length > 0 && (
                  <p className="text-[11px] text-forest-light font-medium mt-1">
                    {occupied} of {room.beds.length} beds occupied
                  </p>
                )}
              </div>
              <div className="flex items-center justify-between sm:justify-end gap-3">
                <span className="font-bold text-charcoal text-sm">{formatCurrency(room.room_rent, currency)}/mo</span>
                <Button size="sm" variant="secondary" className="min-h-[44px]" onClick={() => onApply(room)}>
                  Apply for room
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
