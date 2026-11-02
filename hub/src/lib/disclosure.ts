/** Pure containment decision for an open, non-modal navigation disclosure.
 * Does not change focus, state, authority, or page navigation. */
export function shouldDismissDisclosure(
  target: Node,
  menu: Pick<Node, 'contains'> | null,
  toggle: Pick<Node, 'contains'> | null,
): boolean {
  // Detached/unmounted refs cannot provide a trustworthy outside-click verdict.
  if (!menu || !toggle) return false
  return !menu.contains(target) && !toggle.contains(target)
}
