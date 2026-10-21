import React from 'react';
import { ContextMenu as Primitive } from 'radix-ui';
import { cn } from '@/lib/utils';

const ContextMenu = Primitive.Root;
const ContextMenuTrigger = Primitive.Trigger;
function ContextMenuContent({ className, ...props }) {
  return <Primitive.Portal><Primitive.Content
    className={cn('z-50 min-w-56 rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg outline-none', className)}
    {...props}/></Primitive.Portal>;
}
function ContextMenuItem({ className, ...props }) {
  return <Primitive.Item className={cn('relative flex cursor-default select-none items-center gap-2 rounded-md px-3 py-2 text-sm outline-none focus:bg-accent data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4', className)} {...props}/>;
}
function ContextMenuLabel({ className, ...props }) {
  return <Primitive.Label className={cn('px-3 py-2 text-xs text-muted-foreground', className)} {...props}/>;
}
export { ContextMenu, ContextMenuTrigger, ContextMenuContent, ContextMenuItem, ContextMenuLabel };
