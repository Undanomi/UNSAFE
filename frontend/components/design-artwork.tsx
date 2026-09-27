type DesignArtworkProps = {
  variant: "infrastructure" | "machine" | "machines" | "security"
  className?: string
}

type CircuitFrameProps = {
  className?: string
}

type MachineHudDefinitionsProps = {
  prefix: string
}

function MachineHudDefinitions({ prefix }: MachineHudDefinitionsProps) {
  return (
    <defs>
      <filter id={`${prefix}-line-glow`} x="-80%" y="-160%" width="260%" height="420%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="3.6" />
      </filter>
      <filter id={`${prefix}-node-glow`} x="-260%" y="-260%" width="620%" height="620%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="5.2" />
      </filter>
      <linearGradient id={`${prefix}-line-natural`} x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" stopColor="#91b8d5" stopOpacity="0.9" />
        <stop offset="0.28" stopColor="#829fba" stopOpacity="0.84" />
        <stop offset="0.7" stopColor="#758ba5" stopOpacity="0.79" />
        <stop offset="1" stopColor="#7186a1" stopOpacity="0.76" />
      </linearGradient>
      <linearGradient id={`${prefix}-glow-natural`} x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" stopColor="#79bdd1" stopOpacity="0.38" />
        <stop offset="0.44" stopColor="#6ca9bd" stopOpacity="0.24" />
        <stop offset="0.76" stopColor="#628ba1" stopOpacity="0.07" />
        <stop offset="1" stopColor="#58718f" stopOpacity="0" />
      </linearGradient>
      <linearGradient id={`${prefix}-glow-in`} x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" stopColor="#58718f" stopOpacity="0" />
        <stop offset="0.55" stopColor="#628ba1" stopOpacity="0.06" />
        <stop offset="1" stopColor="#79bdd1" stopOpacity="0.26" />
      </linearGradient>
    </defs>
  )
}

const HUD_STROKE_PROPS = {
  fill: "none",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  vectorEffect: "non-scaling-stroke" as const,
}

/**
 * Decorative frame measured from gemini-design/マシン一覧.jpg.
 * Fixed end caps retain their angles while only the two middle rails stretch.
 */
export function MachineListHud() {
  return (
    <div aria-hidden="true" className="slsg-machine-hud">
      <svg
        aria-hidden="true"
        className="slsg-machine-hud__left"
        preserveAspectRatio="none"
        viewBox="0 0 513 520"
      >
        <title>装飾HUD左端</title>
        <MachineHudDefinitions prefix="machine-hud-left" />
        <g
          className="slsg-machine-hud__glow"
          filter="url(#machine-hud-left-line-glow)"
          stroke="url(#machine-hud-left-glow-natural)"
          strokeWidth="4.6"
        >
          <path {...HUD_STROKE_PROPS} d="M14 597V310L4 300V49L31 22H513" />
          <path {...HUD_STROKE_PROPS} d="M41 470V300L16 275V66L43 39H513" opacity="0.28" />
        </g>
        <g
          className="slsg-machine-hud__lines"
          stroke="url(#machine-hud-left-line-natural)"
          strokeWidth="1.55"
        >
          <path {...HUD_STROKE_PROPS} d="M14 597V310L4 300V49L31 22H513" />
          <path {...HUD_STROKE_PROPS} d="M41 470V300L16 275V66L43 39H513" opacity="0.68" />
        </g>
        <g className="slsg-machine-hud__nodes">
          <circle
            cx="513"
            cy="39"
            fill="none"
            filter="url(#machine-hud-left-node-glow)"
            r="6.5"
            stroke="#70ddef"
            strokeOpacity="0.82"
            strokeWidth="4"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="513"
            cy="39"
            fill="#17293d"
            r="6.5"
            stroke="#a9eff8"
            strokeWidth="1.45"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="41"
            cy="470"
            fill="#18283a"
            r="6.5"
            stroke="#718ca5"
            strokeWidth="1.45"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="14"
            cy="597"
            fill="none"
            filter="url(#machine-hud-left-node-glow)"
            r="6.5"
            stroke="#6fdced"
            strokeOpacity="0.9"
            strokeWidth="4.5"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="14"
            cy="597"
            fill="#122638"
            r="6.5"
            stroke="#b1f4fb"
            strokeWidth="1.45"
            vectorEffect="non-scaling-stroke"
          />
        </g>
      </svg>

      <svg
        aria-hidden="true"
        className="slsg-machine-hud__rail"
        preserveAspectRatio="none"
        viewBox="0 0 100 520"
      >
        <title>装飾HUD上部左レール</title>
        <MachineHudDefinitions prefix="machine-hud-rail-left" />
        <path
          {...HUD_STROKE_PROPS}
          d="M0 22H100"
          stroke="#7186a1"
          strokeOpacity="0.76"
          strokeWidth="1.55"
        />
      </svg>

      <svg
        aria-hidden="true"
        className="slsg-machine-hud__center"
        preserveAspectRatio="none"
        viewBox="0 0 62 520"
      >
        <title>装飾HUD中央段差</title>
        <MachineHudDefinitions prefix="machine-hud-center" />
        <g fill="none" stroke="#7186a1" strokeOpacity="0.78" strokeWidth="1.55">
          <path {...HUD_STROKE_PROPS} d="M0 22L47 69H62" />
          <path {...HUD_STROKE_PROPS} d="M16 69L51 86H62" />
        </g>
        <circle
          cx="16"
          cy="69"
          fill="#17283b"
          r="6.5"
          stroke="#829bb3"
          strokeWidth="1.45"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      <svg
        aria-hidden="true"
        className="slsg-machine-hud__rail"
        preserveAspectRatio="none"
        viewBox="0 0 100 520"
      >
        <title>装飾HUD上部右レール</title>
        <MachineHudDefinitions prefix="machine-hud-rail-right" />
        <g fill="none" stroke="#7186a1" strokeOpacity="0.78" strokeWidth="1.55">
          <path {...HUD_STROKE_PROPS} d="M0 69H100" />
          <path {...HUD_STROKE_PROPS} d="M0 86H100" />
        </g>
      </svg>

      <svg
        aria-hidden="true"
        className="slsg-machine-hud__right"
        preserveAspectRatio="none"
        viewBox="0 0 243 520"
      >
        <title>装飾HUD右端</title>
        <MachineHudDefinitions prefix="machine-hud-right" />
        <g
          fill="none"
          filter="url(#machine-hud-right-line-glow)"
          stroke="url(#machine-hud-right-glow-in)"
          strokeWidth="4"
        >
          <path {...HUD_STROKE_PROPS} d="M0 86H17L64 39H182L214 71V213" />
          <path {...HUD_STROKE_PROPS} d="M0 69L47 22H199L231 54V244" opacity="0.72" />
        </g>
        <g fill="none" stroke="#7186a1" strokeOpacity="0.72" strokeWidth="1.55">
          <path {...HUD_STROKE_PROPS} d="M0 69L47 22H199L231 54V244" />
          <path {...HUD_STROKE_PROPS} d="M0 86H17L64 39H182L214 71V213" />
        </g>
        <g className="slsg-machine-hud__nodes">
          <circle
            cx="214"
            cy="213"
            fill="none"
            filter="url(#machine-hud-right-node-glow)"
            r="6.5"
            stroke="#6edceb"
            strokeOpacity="0.72"
            strokeWidth="4"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="214"
            cy="213"
            fill="#17283b"
            r="6.5"
            stroke="#9fe7ef"
            strokeWidth="1.45"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx="231"
            cy="244"
            fill="#8de5f0"
            filter="url(#machine-hud-right-node-glow)"
            opacity="0.52"
            r="5.5"
          />
          <circle cx="231" cy="244" fill="#9cecf5" r="3.4" />
        </g>
      </svg>
    </div>
  )
}

const HUD_CORNER_PATHS = {
  main: "M609 98V554L584 579H42L8 548",
  upperBranch: "M589 12V159L609 179",
  upperBreak: "M569 179L583 203V326L598 348",
  lowerBreak: "M583 370L590 377V533L567 560H369",
  lowerBranch: "M52 555H284L309 579",
} as const

const HUD_CORNER_STROKE_PROPS = {
  fill: "none",
  strokeLinecap: "round" as const,
  strokeLinejoin: "miter" as const,
  vectorEffect: "non-scaling-stroke" as const,
}

/** Bottom-right HUD decoration measured from gemini-design/マシン一覧.jpg. */
export function HudCornerDecoration() {
  const paths = Object.values(HUD_CORNER_PATHS)
  const normalNodes = [
    { cx: 589, cy: 12, r: 6.5 },
    { cx: 8, cy: 548, r: 6.5 },
    { cx: 52, cy: 555, r: 6.5 },
    { cx: 369, cy: 560, r: 6.5 },
  ]

  return (
    <svg
      aria-hidden="true"
      className="slsg-hud-corner-decoration"
      preserveAspectRatio="xMaxYMax meet"
      viewBox="0 0 630 597"
    >
      <defs>
        <linearGradient
          gradientUnits="userSpaceOnUse"
          id="hud-corner-main-stroke"
          x1="609"
          x2="8"
          y1="98"
          y2="579"
        >
          <stop offset="0" stopColor="#a9eff8" />
          <stop offset="0.42" stopColor="#8aa8bd" />
          <stop offset="0.72" stopColor="#798ba3" />
          <stop offset="1" stopColor="#7186a1" />
        </linearGradient>
        <filter
          filterUnits="userSpaceOnUse"
          height="757"
          id="hud-corner-wide-glow"
          width="790"
          x="-80"
          y="-80"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="10" />
        </filter>
        <filter
          filterUnits="userSpaceOnUse"
          height="697"
          id="hud-corner-medium-glow"
          width="730"
          x="-50"
          y="-50"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" />
        </filter>
        <filter
          filterUnits="userSpaceOnUse"
          height="80"
          id="hud-corner-node-glow"
          width="80"
          x="569"
          y="58"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="12" />
        </filter>
      </defs>

      <g className="slsg-hud-corner-base" stroke="#52627a" strokeOpacity="0.62" strokeWidth="1.55">
        {paths.map((path) => (
          <path {...HUD_CORNER_STROKE_PROPS} d={path} key={`base-${path}`} />
        ))}
      </g>

      <g
        className="slsg-hud-corner-wide-glow"
        filter="url(#hud-corner-wide-glow)"
        stroke="#79bdd1"
        strokeOpacity="0.22"
        strokeWidth="4.2"
      >
        <path {...HUD_CORNER_STROKE_PROPS} d="M609 98V554L584 579" />
      </g>
      <g
        className="slsg-hud-corner-medium-glow"
        filter="url(#hud-corner-medium-glow)"
        stroke="#79bdd1"
        strokeOpacity="0.3"
        strokeWidth="3.2"
      >
        <path {...HUD_CORNER_STROKE_PROPS} d="M609 98V554L584 579" />
      </g>
      <g
        className="slsg-hud-corner-subtle-glow"
        filter="url(#hud-corner-medium-glow)"
        stroke="#6ca9bd"
        strokeOpacity="0.08"
        strokeWidth="2.6"
      >
        {paths.slice(1).map((path) => (
          <path {...HUD_CORNER_STROKE_PROPS} d={path} key={`subtle-glow-${path}`} />
        ))}
        <path {...HUD_CORNER_STROKE_PROPS} d="M584 579H42L8 548" />
      </g>

      <g className="slsg-hud-corner-core" stroke="#7186a1" strokeOpacity="0.78" strokeWidth="1.55">
        <path
          {...HUD_CORNER_STROKE_PROPS}
          d={HUD_CORNER_PATHS.main}
          stroke="url(#hud-corner-main-stroke)"
          strokeOpacity="0.9"
          strokeWidth="1.55"
        />
        <path {...HUD_CORNER_STROKE_PROPS} d={HUD_CORNER_PATHS.upperBranch} />
        <path {...HUD_CORNER_STROKE_PROPS} d={HUD_CORNER_PATHS.upperBreak} />
        <path {...HUD_CORNER_STROKE_PROPS} d={HUD_CORNER_PATHS.lowerBreak} />
        <path {...HUD_CORNER_STROKE_PROPS} d={HUD_CORNER_PATHS.lowerBranch} />
      </g>

      <circle
        cx="609"
        cy="98"
        fill="#79bdd1"
        filter="url(#hud-corner-node-glow)"
        opacity="0.42"
        r="18"
      />
      <g className="slsg-hud-corner-node-glow" fill="none" stroke="#79bdd1" strokeOpacity="0.18">
        {normalNodes.map((node) => (
          <circle
            {...node}
            key={`node-glow-${node.cx}-${node.cy}`}
            strokeWidth="2.6"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </g>
      <g className="slsg-hud-corner-nodes" fill="#17283b" stroke="#829bb3" strokeWidth="1.45">
        {normalNodes.map((node) => (
          <circle {...node} key={`node-${node.cx}-${node.cy}`} vectorEffect="non-scaling-stroke" />
        ))}
      </g>
      <circle
        cx="609"
        cy="98"
        fill="#17283b"
        r="6.5"
        stroke="#9fe7ef"
        strokeWidth="1.45"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function SvgDefinitions({ prefix }: { prefix: string }) {
  return (
    <defs>
      <linearGradient id={`${prefix}-steel`} x1="0" x2="1" y1="0" y2="1">
        <stop offset="0" stopColor="#b8d2e7" />
        <stop offset="0.45" stopColor="#607f9c" />
        <stop offset="1" stopColor="#223650" />
      </linearGradient>
      <linearGradient id={`${prefix}-panel`} x1="0" x2="0.9" y1="0" y2="1">
        <stop offset="0" stopColor="#365777" />
        <stop offset="0.48" stopColor="#1b314c" />
        <stop offset="1" stopColor="#0c1930" />
      </linearGradient>
      <linearGradient id={`${prefix}-edge`} x1="0" x2="1">
        <stop offset="0" stopColor="#5d8ac0" stopOpacity="0" />
        <stop offset="0.5" stopColor="#86e9ff" />
        <stop offset="1" stopColor="#5d8ac0" stopOpacity="0" />
      </linearGradient>
      <radialGradient id={`${prefix}-halo`}>
        <stop offset="0" stopColor="#6fdfff" stopOpacity="0.42" />
        <stop offset="0.46" stopColor="#4e87cf" stopOpacity="0.14" />
        <stop offset="1" stopColor="#0b1326" stopOpacity="0" />
      </radialGradient>
      <filter id={`${prefix}-glow`} x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="5" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
      <pattern id={`${prefix}-grid`} width="34" height="34" patternUnits="userSpaceOnUse">
        <path d="M34 0H0V34" fill="none" stroke="#5a7ca4" strokeOpacity="0.16" />
      </pattern>
    </defs>
  )
}

function Rack({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse cx="67" cy="178" fill="#559fd0" opacity="0.16" rx="88" ry="25" />
      <polygon
        fill="url(#infra-steel)"
        points="0,25 54,0 134,32 80,59"
        stroke="#8fb5d2"
        strokeOpacity="0.48"
      />
      <polygon
        fill="url(#infra-panel)"
        points="0,25 80,59 80,182 0,147"
        stroke="#7397b7"
        strokeOpacity="0.48"
      />
      <polygon
        fill="#142a44"
        points="80,59 134,32 134,153 80,182"
        stroke="#6e91ae"
        strokeOpacity="0.38"
      />
      <path d="M12 43 68 67V82L12 58Z" fill="#09182c" stroke="#6d8ca8" strokeOpacity="0.35" />
      <path d="M12 67 68 91V106L12 82Z" fill="#0b1b30" stroke="#6d8ca8" strokeOpacity="0.35" />
      <path d="M12 91 68 115V130L12 106Z" fill="#0a192d" stroke="#6d8ca8" strokeOpacity="0.35" />
      <path d="M12 115 68 139V154L12 130Z" fill="#0b1b30" stroke="#6d8ca8" strokeOpacity="0.35" />
      {[0, 1, 2, 3].map((row) => (
        <g key={row} transform={`translate(0 ${row * 24})`}>
          <circle cx="21" cy="52" fill="#68dff7" opacity="0.85" r="2" />
          <path d="M29 55 58 67" stroke="#52718e" strokeWidth="2" />
        </g>
      ))}
      <path
        d="M92 68 123 52M92 84l31-16M92 100l31-16M92 116l31-16M92 132l31-16"
        stroke="#6986a1"
        strokeOpacity="0.48"
      />
      <path d="M9 33 76 61" stroke="#b7e8fa" strokeOpacity="0.42" />
    </g>
  )
}

function InfrastructureArtwork() {
  return (
    <svg aria-hidden="true" className="size-full" viewBox="0 0 1000 520">
      <SvgDefinitions prefix="infra" />
      <ellipse cx="725" cy="220" fill="url(#infra-halo)" rx="365" ry="240" />
      <g fill="none" stroke="#4d729b" strokeOpacity="0.35">
        <path d="M126 420 430 245 785 420 594 520" />
        <path d="M268 500 575 322 887 474" />
        <path d="M448 129 735 295 976 156" />
        <path d="M455 345 618 439M557 286l167 96M681 224l163 95" />
        <path d="M657 140v280M813 56v340" />
      </g>
      <g fill="#7ca0c3" opacity="0.17">
        <polygon points="208,310 267,277 355,320 296,354" />
        <polygon points="260,360 320,326 407,370 348,404" />
        <polygon points="111,394 168,362 253,404 196,437" />
      </g>
      <Rack scale={0.92} x={466} y={142} />
      <Rack scale={1.15} x={648} y={170} />
      <Rack scale={0.88} x={835} y={52} />
      <Rack scale={0.82} x={888} y={318} />
      <g opacity="0.55">
        <polygon fill="#7990a9" points="310,130 378,91 468,132 397,173" />
        <polygon fill="#253752" points="310,130 397,173 397,206 310,164" />
        <polygon fill="#172b44" points="397,173 468,132 468,165 397,206" />
      </g>
      <path d="M0 36h290l25 25h248l22-22h310" fill="none" stroke="url(#infra-edge)" />
      <circle cx="300" cy="46" fill="#8eeaff" filter="url(#infra-glow)" r="3" />
      <circle cx="872" cy="447" fill="#6edcf6" filter="url(#infra-glow)" r="3" />
    </svg>
  )
}

const MACHINE_LIST_ARTWORK =
  "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAHQBHEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD4ExSMTjFKf1ppr6A4xpJoyaWkpAGTRz1ox70daYwzRk0HmgYBpAGTQTS0hoATNIe/rSnmk9aAG80tJS46UgAnNJzS/XiigBKSlIoNADT1o5/Cg9eaKAD+VAye1GPXpRigAxRR1oNAwoo60UCFoBNGOaPegYtGaMUc0CDn60DPFAFKKAExSjNGPWjFAB0peaMUYoAXmj3oAox3NAB2oo6UEZGe1ABzS80UuKACl/lRj1pQPWgAGaXtR+tLQAgNLRiigBc4pwpvvSj3oAcKUGkpeaADnvRRQPegBaPTFBPNJmmIWlDU3NJ3zQFh+6lzkUzP4Gl6fWkA8GjPtTM+lOBpgO9aM0mf/wBdL1pABNNzn2pelNP60wDNJnFKetAoAAaOtFFAAaaeKUjikPSgBO9GeaM80lADs80uTSUZoGOyTRzSUUxC5pM0CjikAoozQOlJnNAC5/KjNLjNJQMM5oFFLQIXJzS0lLQAg6YpaTNGaQC5NFBoznNAxM0v86KTNABmnxH517c0ynQn94v1oA6GM4UeuKcDxzUEshiiLDsOlNgvVnGD8p9DQUWh+Roxn3ox15o4oGHTmo89MjFS9fwFNIz2pAQSQrIPmFVJrNkJK8itEAUlArGMcg85zSBskc1qTWyTDJGD6iqUtq0RzjI9RQKwwEk08HrUfTNLnFAh5bJpCaVUaThRmrMVnt5fn2phuV0iaQ8D8aspbBACeTUwG3gCjcCKVx2GgYHtQTQ3X0qKWUJkdT6CgoXPvxUMk6r0GTUEkzOcdBUZPP8A9egm5K8rP3zUW8nt9KVvzpB360AMmOVqv07VZm+6KrkdKBCUmaXFJjimAmaP5UGg0AJmjJFGBR1oAM0ufrSdeaXPFABmgE4oooAM96MmiigAzQaKOtADTRS0mBQAZ5ozRikoAPwo60GjOKQCHpQD0+tFFAybPvRTd1FMRD1ppBANOxSbaYhpGfejj1oIoxmgBOpo6ntijFHSgBxGMUgoxmkP0oAXFJS9QKDQMae9IeRS4pOtACfWlpKOtAC0n1pTQBx/nmkAmaTilpODQMQ0UppOtACYo+tKBnrRjIpgJjNKBkUYoxSAO5o9e1GKAOaYWDGaMd+lAHNGKBC4pR9KTGaXFIAApcUfhS0hiYpcUfhS4oEJj2o7+lGKWmAmKXHrR60cUAGKUjjpRx/+ulxQA0cUuOlGAaUYzQAoFL2zRilx7UAJil6jmjFGMUAFL1pKXFABjninCmgU6gBaWm4zTse1ABQelHFFACGkzQfyooACe9L1pOtLimAv4UAGgCl4xQAgNL2FJil/CgQvSl7UmKBQMUk0hNHWikAlA60uKTrTELmijFGM80AIenApKccd6aR60AJ3oHNBFGPWgBaKBRigBaBSAUuKAD0oxSgcUuBQNCHk8UDvRij60AAo+tHHpS8ZoAKUCggZooAKKUUUAITRRiloEJR9KOtGKQAKMUYo/lQAhqSH/Wpj1qM1JaqPtEf1pjNe7P8Aoz/SsyMkgVq3QBtpPpWXByfQVIMtQXrxABvmHoavRXCTjg8ntVFrQldwG4VAVKHjg+1A7mzkilzWdDfsnD/MPXvV2OVZQCjZ9qBpkp54pKTkUoO4UDExnrSYyDxxTsA0u0GgCpNZhySvBpkdjg5f8hV/GBzTW96BWTI1RUGAMUp44peDnimOQvU496BgxwTTHkEYOTxTJbjg4PbrVUk55NAmyWS5ZuBwPWq7Hv3pSeaaelAhOaYTTm6cU08mgAzxSjk5xnNNx/8ArpVHPHFCAbMflqE8/Sppc7RxUO3imIaevejGMU4jmkxSAaeOvFNPH0p22jbQAzpTgM0Y/CjFACfmKOtLwKOKAE9e1LRj1FGBnpzTAXHrRjNGB6UYFIA7UhH4UuBQRimAmKOuaUijrSAaR0zSEcU7FH1FADO3NFOwO9IVoGNyKKUrn60GgQ+il/z1ooGQ896Q80Gk61QhCDSdc5p9NJzQAnWilPrmkPNAB1ox0FHWkxQAvNJ1xmlx+dJjmgAx+NJj86Uik/SgBO3pS0UUgAik+opTSdaADFIfpS0lACUEe1BopjDHFBGfpSn360hoATmlx+faijPvQMPaiiigQUc0dKKBABTsE02nDmkAvP4UuMUnajtQAoHtR+FGaB0oAOelLSZxS/WgAxQOlFFAC4/CjFFKATQAAZpR/OgUo4pAAFFHQUUwFxR2oo60AFLSAe9KOKAF60e9L1oxQADpRSUtAC5pM80daOtACEmlxwaXGTQcmmAmOOlGOaXHrR9aQC4z1FGPajPWlzQAlLSU7rQAmKKWg8UAJS4pPxpaADtSYoAopgFBoooAQ0macaQ0AJ1paSigBcZo+lANLQAUcmjFKBQAmKXGaXmikAfeo69qO1L2pgJSUvWigAAzRRS0gCil70YzTEJijFLilxQAmM0n6U7GaTHNIYmM0HoadimkdaYCDmpbXm4j+tRVLa/8fEf1oA17of6PJ9KzLcDODkVq3Q/0aT6VkxHA6cUgNFIpYRvhbevdaeHgvDhh5Mvv0qnFO0Z3KcGrBmiusCVdj/31pCIbizeInPIqAFomyCVrQHm268kTRHuOajkCS8r+VAgh1DOFkHH96rqOrjKkEe1ZLw4Ge1IkjwnKnFBaZsn6UH1xVKHUFcgP8p9auK4cAjke1BQpFNbjrTycdqqXEhJI7UAPlnUAheTVZ3aQ8n8KQ/55pD+VAmRnOf8ACk4PanGmmgkb06Uh60p5600jHPegY3t7U0nmnnmkx+dAgA464FAGBx196aw9OaFX1oAJSNtQHtU8h+T2qE80wYdKTOKKCM8mkAnWgjHWjb70vSgY3/OKTnFOI5oAoAbjFGKUrk4p6Rs5AAJNAiPBoq5/ZkxXdt49B1qs0bISCMYoAb1ozilxjNJk56UDDt0oobmgcUAHQ0Yoo/SgQmKOvWlpO3PFACEE9qKX9KSgBP8AGk+nrSmkPIoAkopc/WigCtRSH6UVYgIpD1p2abmkMOtGKOtJnmgBcGkP+c0pNITQAbaXr9abyfrRzQAhANFJS5z9aAEpSM0GkzSACOlHXtR9aTj8aAFpKD7ijPagA+tFB5opoBKXtSYo6/SgAxmjtR2o/wA4oGJS0ZozQAUdKM/nRkmkAfrTgOabzS85FAC9etOA9aaPrS5BBoELS4HTFJ39qUGgAxmlpKM5oAMUoHNJ1+tLQADmnYpg60/r7UALQMdMcUdaX3oATvS4pKOKAFNHXtSd6Xg9qAHD0pcUg9qWgAxkUGkzR1NAC88UZoH5Uo6UAJigCginAGgA/DmjAoOaWgBMZOMUopPpRQAuKTrRmjNACg4pRSUo+tAC0GgUhoATpRQTx0o70AOAFJSd6M0wFoNFFMBDwKSlpMccDmkITFKOo44pD0NKOfb60hjsUbaUgmgUxCYpcUdaXpSGBFAHtmjNGeaAFxRgYooNMBPpRijFKKYCYpcUUoHNIApcUYpce1AhMUUuKMZNACYFFLgcUY60gG0hApx6e1IRQMaRUtr/AMfEf1qM81La/wDHzHk96YGxdj/RpPpWXbgMME1rXYzbyfSsqDaMZ6VI2SSWzIBxx61GQcntV6MTRKWQeZH3WlEEN3/qz5cn9w0ElaC5aE8H6g9KmZklOVGw9wOlQzWzxEgjBqMFlx7UAix0PNDRB196iWUkc1KGx0pDIGtyvSlhmeBxjpnpVjdkYqGUDcCB3pgaoGVBPWqc+A/TFXQPlH0qlOP3hoKZETz0zTWznjtTjTTzQIaeOtMPenGkP0oAZjjNIPSntimHk9xQIaRkUmM07HpTT1xigYbQD7UDp7UfpTTnPSgLCzH5agxU0g/d1CRkd6BCCj8KD+VFAwpMA0vSlxTEJilCnPSrFvZSTngYX+8a1LexjgGfvN6mkVYoW2mvJguNi+/U1pw2yQgBRj3qUDnFGDx6e9IdrDcAHjGKintY7hSGH41MOPpSkE44oGYtxpzxZKDev61TKHvXSYH4VXuLGOcEj5WPcUEtGERSd6tXFlJBncuV9R0qsRimITFJilIooAQL0oJFB5pNufwoELx/+ukPHNGMdaXg9aAGmjtRQfpQMfRRz6migZW/GgelGOKQ+9WQL1FGSeKCKM+1IYZpKXrSGgA7UnWlwKTuTQAhzRngUuMikoACMn+lIehHenHmkPrQAztQcGnYpOKQCDpzQ3NBxil/SgBBxQelLmigBByOaTHFKSKTjvQAuM0h69aU+9BoATNA6GlPNJ9aBiHk0HOf50vHek4PXvTAXPtxR1HSgdTR70hBTs5pB70YHpzQAoNKBSKMZ5paAF5/+vSck0v1petAwxmjnNBHqcUdKQg9KOuaKXqfrQACnfWgcc4xRgUwAGl60YHegj8qAA8e1HGaXINJ9elIEIOelPApAKcozTAPxpcd6CgJzjFKV5FIAxSAetOA4oA60wEINIOR0p+3P0oIyKAGAkjinA8Zox68U4LQA057dKXGaAMkHv707GOtIBpozR656U7gdqYDccUhNBGeaUDjkYoAM0o6c0gHHpTqYBgdvzpDxSj9aDg9aQCdeaQ8ClpD+QoAQkkmlFLjJzSYzTAM+tGc0EUg9aAHZpO/SjHFHWgQZ5pwHXA4pMZpRj8aBh057UufWkNLnigBMUhyelL6UDnmgAGacOc0mM0oFAARz3oxRilxQIQcd6Pw5pwFJ3z0oACOKMdwRSmkx09BQGo4YpCemeaXtTR15osA7PNGe2KBR2oAOlHSkA6UuO9MBvOfY0Hr0pc+1ITjipGISKltT/pEf161GaktFH2mP60wNy5U/ZZD2xWPGOK2bkYtpPpWPFlvrUjZYhuWiOVYirREF5y37qT+8vSqL27Rn5hj60m4g8ZoJaNBpJrcbZl86Ps4pjW6ON0ZyD2qG3vXiOPvKezdKnKxyHfF+7b+72oJKrx7SaaGK1aPU7hTWjBHoKQxsMqnIbv0qOUguAOlI8JXkE8VFghhn1plG6B8g+lUbgfvDV8Dag7cVn3AzI1BRCT2prH8qcRTTxSEIaacHtTsg9KTrTAacZpMZPrTjSfTFADSKbkZp5A/Cmkd6AGE4/8Ar0fhS4z9KUYxQBG+CtREVNKflz2qEqaAENAGKcqFjgAknsK0LbSixDS/KP7o60AUYbd5m2opY1p2+mLHgyfM3p2FXEjWJNqKFHtTuTz2pFWsNACgegpQMj+tKQO9Qy3CxHrz6UhkpO0+lQyXYj96pz3TSE4OBVVnJNMTZpLegmrCSq461ih6minKdeKLCua4x34peMZ6Gq0F2CBu/MVZUhxkc0D3GsBzkZB7GqN1pKyBjEdrenY1fIo/SkBzUsLwNtdcGmYrpZYVmUqygj0NZk+lMmWi5H909aoVjMI5ox7VLIhU4YYPvTNvrQIYT0zS8HtzQR60c0AIRQelHvmj/GgB+PpRTsUUD1Kveig9aTGfYVZIUDFGCaMc0AJwKSlxRjPtQIT0pCMUuOaTFIYmcmlA9qCKTrQAlBpSM0EUgG0E0vQ/40UAN60E0uOaMZ6igBM+1HfmigZoACaO1BHPtRQAo55ozTTzS0DQZo/Ck6j0oNMBaSjGRR70gAUuKTGaMUAH0pQw6YoC0baNxDqDxSAd6UjikMATQM0AZpeppiDNLjp60dKPrQAtKDzSbc0vOP60AL2pR70Yo60AFGR36UntRgmkA4DHejpxSDilzQAD9aeo5phyeO1SxjIoAdjil6il2569KNuaYDcc0uB6Uu31pdv5UgG7Til2+tKF6UbPagYgFGP8mnBfypxXPWgQwClIwPegDGadgnGaAGAZPSlKDBpTkH1oxnOeKYEPQHijrzilNGOaAAClHPSj9KWgBvJPTFBPWnUhoASjtSEE0DrQAufY0Z5pcUhFMBOKMUu2jHPSgBO1A60YoApAO6UdKXGaMUAJkUHnNIRzQTn60wFGCaWo+1OHSgBcjAp27nHek5AoA4/zzQAu7Pal+tIBTuaADn0oJpcmjbmgQmaBnOOmaAvFL0pgGCMUCjrmjjigAAwaTJJ6YFLRQAg54xxS0hzQcjoaAAUvrSAUHpSAYSKmtf8Aj5j+tQmpLMf6VHjrmgZ0Fzxayf7tYsC7j7VsXSf6NLz2rEiJqRs0kle2ULNH5sB6H0pzWMdwN1u+8f3e9QW940Q2n5kP8LcirKwRTNutnMEv90ng0EspvAyMQw5pUcoeuBV95WU+XdxbW7OBUU1mpGUIK+opEkayhhyaeDnvxVcxFT6/SlDlRxQUiwcEciqkq4cfWrEM68hqhmOWGKBmyF+RazrkHzmrUAwg+lZd1xK1MZAwzx1qM5z7VKx60w8/SgBnelPFKaQZ6Z4oAKDn0oFLQAzGaQjFPIzSYoAYVz7UBBS7cmp4bN5jwOPU0DK0i7l4qW302Sfk/Inqa04bGOLBI3N6mrGKAsVre0jth8o57sepqbbTiKDheScD1NK5Q3bntTJJEjUljgVBcagqAiP5j69qzJZ2kbLMSaBXLdxqBbhPlHr61RaUt3pmSe1KqkjnmmS2ByetKEJqQR+tOx3pCI9lJzUhUmmshPNMBEcqatwXJXHOKpYOKVeKBpm1HOsg5GKmxWLHMV71oW90DgE4oKTLXSkCgU/KtyMUdeopXGVrizjuB8y8+vesm602SHJUb19R1rdOcimtyc9hQhNHLsvNIRg81uXOnpNuK/I/qO9ZNxbtbPtfqemKZNrFfrziloPOOKMUAiXHtRS59jRTHqUv85oHvSgfhSfWqIClooxQMKQ+lKeaMc0gEx2ppzinYowD+VIBlFKRxSEdKYB1pOo5pcZoPNIBDSGlPNJQAUHmg0HnNACUn8qWk4PagA60daKQ0DFxjrSdqOuaSmAp/Wlz1pKOvWgYdetKBxSGjrzQIXA70YoFKBSABS4zRRj1oEL1o5oxS44NAxOv0o60pHFLigQYzRilxRgUAIOKcBxRR1FAB2NL160maKBi96ByelIaByaAHe9AFAo7GgBRUsdQip4SOaQEoHFAHftRt9OKdxzkYoENxmkC5+lOxSgD1oAYMk07PA4pxUetAUUAMCgjgU7YT3zS/pTgCaAGhSTQVIBp2P50EYpAMx0oZeDT9mOaGHFUBVpcUGjPFABQKKKACkPSloPPagBO1KOaQ0vQ0AGKMcUdaXGR6CgBMUhFKBS4oASjHFOIzSYpgJ1opcf/AK6DSAYTzRTtpzVux0qfUG/dp8vdz0oApY9Ktx6bdOhdYHK+uOtdNp+gwWeGYebL/eYcD6CtRU+UcUXHY89KlSQcjHUUo55rs77R4L4ZZdkn98da5+90O4sznb5if3lFFwsZ2Mn3o7mpdh9KaUIpiGAUv4YpelJwaBBj86WkzQDzQAp6exoNApDTAXr9aaTinUh6UAJig8fSiigYA4obgGjH4Uh6daQEZqWyP+lx/wC9ULVPZf8AH3F/vUgOguubWT/drCgG84HXtW/dD/RpfXaawrVMt6UhseUZOo/GnRylT1xVsTiL5J0yv96h9PEi7oGDD0oIZNBqO5fLmUSxns3apDbKh327koeqHrWWUeLqCDUkdwyN1/GkKxbwrdeDUckIP1pRMr5PenCkUVJImXNR7jkZ6CrzLkVWmTDDtzTGb2PkX6Csm7/1zVrYyiYPYVlXeDO3pTKK55+lNPFPxTT1oENxSUuM0UAJ2paDRj3oAKMUuKMcUAIo5FbSY2jFYo5IrZU4AFA0PAPeikB59qdkEe9BYg5pGjDjDDI9DTs8U7qKkDMudMyMxH/gJrLliaNirAqfeumK+veoZreOYYddw/Wnclo5sLxUyEKOlXLnS2T5ozuHp3qiwKnkYPvTIehJv3GngZqEcGpA5IoEOOBTQC5woJNOjQOeW2ipTcLECIx+JoEMa3EYJc8+lQNUjSFySec0sVu8xwgz/KgaIRVu3tJJOQML6mrlvpyxEFvmb36VcwFHFK5aRFDB5S4J3fWnkdxT6Q4A7UFDMYNISAOcVHNcxxZ5yfQVQnuXm6nA9BQFyxPeqmQg3H1Pasi9YyNljk1ZIH0qrdHoO9MkrH2/lSH7p4pcg/QUNyKBIfRRk+9FBepWxmijvRVmQmOB6+9Ljj/GiikAYzSY70uaMUAJigrml5JpOtACFT9aQjHtS4x0zSE5pAJj2pD1pefWj+dAxMUhpSM0hoAMc0nWjFB5oATrR+FFJQAh4FB96DRj1oGGQTSUtB5pgGaQUGloGAoHNFHSkIcB60oFN9e1OxQIUilxSUUAGKMc80d6M57UAGM04DNJSjrzQA4UppM0YpAFHWjHNFAwzzRRR17UAGcUYxSA807tQAD6daUYNJ1pR9KYDhipoBkk9Khqe35JpAT7Se1AXjmlC8UEAUANK89KMY6cU/Ge9LtBz60hWI8A4z+VOC+lLsz2qeO0kkGVWgCuUzilC4p7xNG2GXBpNuOM96YCFe9IRkehpxPvSZ5pAJtx60Mvy0o/l0pH4BFMCqaM0H3ozx6UwD+VFHU0UAL0NH4UuKQnrQAdKSlJpvegYuc9qXPFIaO9Ah3XtSg8U3qKXr7UAFFLinIhdgqgknoB1pgNxUkNvJcyBIkMjHstbOneGpZsNPmNP7o+8a6S106KzQJEgQd/WlcaRhab4WC4e6O89fLHT8a31hWNAqqFA7AVPsA+lJgAZzzUjIfLxkGjafWorvUY7YEE5PoKpR6sWc9Me1AGntoKcEEcd6ihu0kHXBqwDkcHIpjM+80SC8BIXy37MornNR0mewJ3rlP746V2wYDOe9JKquCGUMD1B6UXFY85YYppNdRqXhxJdz2x2N/cPSuZuraW1kKSIUYdjTuTYZmlzTM0uaYD6N3Wm5oyaAHUlFLQAnel4NH60YoABzSHp607FNJpANIqayH+lR/UVCemansv+PqP/eoA37lf9Gl/3TWFCxU10E/FrJ/umsGBdxwKQ2XoLoY2yKHQ9QamWyG4yWcuG6+WxrPZCh5zSxylGyDj6UtyC8ZVkPl3EZjkHU9KhmsMcqcj2qdL9ZlCXCh17HuKe0O0boW8yP0J5FIVzMKNGTmpUmI4NWTh+oqGS1yMrTKQ9CJM1BcjDD61ES8J7ikaUyEZpjOmXmJfXFZN2MTt9a1Bnyl+grMuuZ2+tBZWIpCM05hxTSDQSNpPpTiKKAG9aBzS4zmlAoGGKTHWnYyaDyDQIYvBHpmtY8CstRyPrWo4yv4UDQyG5jm+6w3Z6HrU4BzXOBjuyODnrV631N48CT5l9e9A7mwOtKCPX8aghnSZcoc1JSC477w6daQjv3oHXrmndRQMZg1DcWEdwvK4bpkdasY5p2304FAGDc6bLb8j5k9RVbGDXS4HOaq3GmxT5I+RvbpRcmxjZzTlUyHAGT6CrselPvO8gD271oQ26QLhVx707iUSjbaX0aU/8BFXlRYxhQAPSnkflTcetIq1hSc8U3PrS5A68AVWnvlThPmI70DuWHdY1yxAqhcXhf5UG1fU9agkdpDljmmH2FFhCYJGSeaKQt+lRtKPpTBjyeKr3IHap1+YVBd4AFBJWYUho25oP9aARLn2NFGR6GinYCmBRS5o7+tMkM9PSjp2oJ//AF0dvagAHBpcU3rQSMigBcUHpR60meBQAUnalpDQMbjrR1opKQC03mlNIaACkoOTSUAFHNHekxjNAwNJQaKADrRR3oz1pjDrxRmkooAX8aXGOtJ3o7UgFx6frTgBSA8UZGMUEi8UuM9aTI5ooAOvalxk+tJ3pfxoAXvSim+lKOaAH5ozSUDpQMWjNJS0gDrQKD160dKBhQeKSl6igAHHvTgaaOgzSg857UAPzU9t1NVxyKntTycUCLQUZpdopcelPWJnbAByfSgBm05qaK0knPyg49avWukn70vTsorQRRGAqgACgdilbaakPL/MevParewcdPSnEA//AFqQ546YpDGSW6TLhhkVn3GksuWjG8enetQL06inKRTA5p4ivGCCO1NxgV0dzZR3KncMN6isq50ySDJA3p6igixR6fjTW+6acykGmNkA80AVj1pO9BzQM96YDhSgelNpwoAO1ITSmk6UAH4UE59qTFFACk9fSgdaaTRgmgB69ad2qew0+fUJNsMZbHVugH1NdTpnhmC2w8376Uev3R+FK49zA03QrjUCG2+VH/fYdfpXV6bo1vYAbV3Oert1q+sYUYxTv0FK5VgCAcYpxXjNNeVYlyxwPWsm913B2xf99UIGalxcxQLl2APp3rGvtYLAhCUHrWbcXrSOSW3VUaUtnmixNySe53McnNQCVgOv40CMu2FySaeYBGPmPzegpkNk0F+UIBrXtdRyPvZHoa5thzxTo5mjIIJFA0ztIp1lHB5p5XiuatNTxjdx71tW1+HHPPFBaZa249hVe7sor2ErMgdD6/0q0mHAIOaeEzQUcXqXhaa2Je2Jmj/ufxD/ABrDOVYhgQR1B4r0/wAoelUNQ0G11JfnTZJ2kTg//XouTY4ANTgea09R8OXWnkso86L++o5/EVmBfamLYf1pRz2pMU7HNMQUdqKM8UgEpDQTT4YHuH2opY+1AEdW7C3Zp43x8oPU0pWCzHzETSjsPuj/ABpbe5eW6jye/AHSkBuXH/HtJ/umsS1UlxjrW5Of9Gk/3TWDE21sj86BtGiHilzHOvlSf3uxqGfT2jJYfMp7g1Kl1HOojuEyP73cVMsM1qN0DefD/dNIzZmCNkPNPSZkbIOK0D5F2OP3cn901Uns2izwaAHrIJOe9Pz61SOUPNSpPxg0DLDIsi8iqU0QR+OmavwKJVY7hkdqp3ZKkZ9etBRuqMxJ9BxWbcj98x61pR58pPoKzrkfvnFMqxXNNNPweetNK55oAYRSCnEZNBFAhMUAU7bRigBMZpcUtNLDBoAReCPrWo3Kke1ZQbkVqt9z8KARz8KhpMHpnmrk1g6JvX5k9RVOEjzORkZ5rVijmgG+1fzV7xN1oBmcpaJsqSp9q0LfVAflmGP9oU3/AEe9Yr/x7z91PSq1xZvASGXAoEmbSFWAZW3A+lOxgisCGeS3bKNj27Vp2upxy/LJ+7b36GgpMvKcdead1HHSmg9MdKN1IoULz6Uu2lBz/hSgHFA0JjPemHIPHFS7SRUUsq24+c4PoO9IBOemMZqCe6SLr8zegqvcXrSZC/Ivt1qoetUIlnuXlzzgelQbc0Y/D60x3xxQIeTzUbyelI0hJwKbJDIse9l2g+tBNyNpMsPf3pZYXhClwy7hkZFSWXlxXMcko3RqckAdat61qa6rMhSLy40GB60CKcX3R/WorvPBAqdE2getRXWMLQMqYpP8acxzyaSgLk2fail49aKdwuuxTAyTSYGBS0opkDcAUbR3p2M02mMOM0Eig8ZxTaQC8YwBSHg4oNJmgYdqQmlpDzSACabnFKT1pDzQAmaM80cUhoADzSZ60p60h5FACenP50UUZzQAU39aXNJQNBjml49KT6ij3oGLRSe1HXrQAvHpS0lLQIXijgdqQcilpAOwDSH3pM0UCFxmlHek60fSmAU4c03j6UtAx3fmigUopAGaBRjrRQAZpRSe9HWgBc+1FITRQAtFAGOKUDg0DFxVmzGXNSWOkT3pBVdiH+NuldHp2jw2Qyf3j/3m/pQBStNLkmwxGxPU9a14LSO2XCjn1qfAApMUihCM5ppUU8rxntRt4BIPFAhm0HtigLz7VJt9qNuaYEe3JpwHNP20baQxqgf/AF6cF4HFOC80oWgLFG60mK4+ZRsf1FYl7YS2udy8f3uxrrAtDxrIpDKCD2NMVjz9hg02up1DwysuXtzsY/wHpXPXNnJauUkQofegmxAOvpSg0nejOaYhd1IxopKQw6UYBoNHQUxE1vay3MmyKNpGPZRmul0zweeHvGz/ANM1P8zWposaW9hBtUDKAkgck4rYjw44qS0iC3tI7dFSNFRR0CjFThAO1S7MA8UbaNxkTBQMnge9Z15q0UBITEjfpWjNCsyMjAkHg1z2p6FNErPbfvV/uH7w/wAaBO5SvNSedjvbIHbtWdJcbj14qCYurFXBVgeQR0pqdcVVrGbZOuZDgZPsKuxacEUPO3lr2Hc1Hb3S2yfIg8w9XPOKXzWlfLEux9aRGpMzgLthTYvr3NRCDzD8q7j69qtrbrEoMzc9o1pzn5Ru/dp2QdTQJsz2tucZy3oKhaAqcHrWiVLHoIkP4satxWKKgZ/3UZ6s/wB4/QUBexhiIjmpobiSJvlOKuX7ROoWGPYB/EerVQIIJIoGnc2rPU8jD8H1rXhuVkHJH4Vy9nazXcgSFC5746D6muo07RPsqhpm8yT0H3R/jS2No3Zb2ZpQmeSOamC/hSlSDSLK/lVk6j4Ytr7LqPJl/vIOD9RW6Riq9zeQ2a5dhnso60A7HCajoVxp2S67o/769KzDius1rU2u7WVAu1MdK5Qjr3qjNqwnelVS5AUEk9hU9naG8l2hgoHJJqSa7WyJjt0KsODI4+Y/4UCEFjHAoa6fbxxGvLH/AAqOa+3oY4lEUXTavf6mqrFnYlmJJ65PWgew4oBCHnrViy4uYj0+YVB0qa2OJ4z7igLHSzY+zSD/AGTWGuB7VvAbl55Heqc2mRvkxny29O1BVrlAAY+tT29y9u2UYioJIZLfO5Tj1HShZAR7+tBFjV8y2vxh18mX+8vSmyRS23DfvI/7wrPBxirMN4yDaTlfQ0E2aEaNJOg/Cq0tsy/d5FWztbJHFJnHWkhlAO8Z7gikeQyEZ5rQeFZRyOfWqU0JicZ9aZSOiRSIk+grNugfPateP/UpgdhWVdL++ahFlcjimHmpSBTSM0CI8ZoxTjTScUAJj8KaSBSNJnpUZbNAh7P15zTScjFIASaeE4INAhoHIJ9a2zjYcDqKx+nbNbR+6R7UFI5dANzfWrcFwYyCCQarR4Eh+tXHs22b1G5PUdqCSz58N4ALiPJ7SLwwqbZNbJ8uLu29P4hWT8yHpVi3u3hbKsQaBWJnghuRuhOD3Q9RVSS3KHkVoGSC7OWHlS/317/Wo3Ur8r4b/a9aQIgt72S24B3J6GtS2vIrkfKfm7g9azHgDVXeNkORkEUFJnRc/Sgueuax7bVWjwso3D+93rTSVZVVgcqaCxk93IpIXj3qi7FmySTVi5OXIqs+O9MCM0jc5/lSSTKue9MhimvH2xqW/kKBNiSSAA0+C0kuBuOEj7u3AqV1tdMP7wi5uB/yzXoPrSyQXF4glvpfs1t2QcE/QUySPz4YJAlrGbmf+9jgVFcI+7NxLvl/uL0FPa7CL5VnH5EXd/4mqKOD1z+NIBh3SdOlSCHAzUqqF6/nTZJODRcNhu38RVe7IwtTr8y+tQ3Q4XPFAXKh+lKB/Ol78g0D+tAifb9KKWimFigKM0mc9aXPrTJDPagikJ/Skz1pjA0nUUHFIeaQwJ/OkNKcU00AJ+tITS5/CkzQAZzR1NGc0gpAB+lB4oNNJ6+lAB0H9aPrSE0vNAB1oxRmkJ/OgYHNJn2oJPpQetAwzQaQUtAB1oPJPFFFABTv500cf40ucZoAWlNJ1FLSEIDjilpM0A0wF/lR+tGaXikAYNKOvSkA9qXqaYDgO1LTaXHFAAOaX2o7UZ4pAGM0GjNJnNABS56036UE0AAOSB6niuo0vQoYwskwEr9cHoK5eL/WLgcbhXZQSsgHNA0aITAx2pwGOgqKK4Dfe4qwBn3oKAD1pQtKEpwFIY3b1o21Jto25oBIj2ZNG3mpdvNG3NAWIwD3pcEVIFowO3WgBm2nBadt5PGKeFoGMC0oXNSBM04JjPekAwDFR3VjDex7JkDj9RUs0sdsm6Rgg96xrvXGc7YPkH949aYmYOv6ONJmXbIHjkztB+8PrWUetX9ckaR4SxLNzyazN2KZmyWimBs04UAHSnAcdqaeOKd29KBHoGm/LYwD/YHX6VejcjkHFULH/jyh/wBwfyqW11C3umZUkG8HBU8GlYu5qR3IIw/HvUxUHnqKo5waljmKdDgelMZYK0hXHB60scyv7GnFc0hmbqOj22oofMTD9pF4auU1Lw7c6cSyjzof7yjkfUV3nl47c0mzI6U0S0meZpJip4pADkHn1rsNS8MW19udB5Ex/iQcH6iuWv8ARrvS2PmxkxnpIvKmq3M3Foljmwc5wfXvVuyt5LxmKbY0X70sh6Vko2cVaSU4C5JUdu1Kxk0bBa1tOYh9ol/56yDgfQVQuJWmJZ23HtTVkBHWtGw0K41DDkGKI/xsOfwFFhqOpjMGdgqgsT2HWtrTPC8k5D3ZMSddg+8f8K6Gx0a208ZjTL93bk1cApX7G8adtyC2sobWMRwxhFHYDrUnl5HSpMenah5VjUsxCgc5NSa6EflVFPNHbLukYKPeqF94hRPltxvP949KwZ7qS4YtIxY+9Fibmpe64zgrANg/v96yJC0hLMxLd6QnPWlOPXJp2EVbwD7PJwenrWEy81u3h/cSfSsNs0yGNBKnIyD6irkd5HOoS7j3jtIv3h/jVPGe2KQ0CLc+lsqGS3YXEPqv3h9RVLGc8VPbzyW77o2KN6irpkt74fvl8mb/AJ6J0P1FAGWRzR06das3VjLbckb4+zryKrkZzQBetNXeEhZfnTsR1rXhniuE3IwPtXMkZNLFK0LbkYqfagdzqWAPDDI9KpT6cr8x/I3p2qG01hWws4wf7wrTUq6hgdw9qB3TMV0eEkOuPek3elbTRo4wwDD0NUp9NwSYj/wE0CKiylT1qVJd3WoHRkOGBU01TjvQI1IIjIMqaqXqbWUHimx3jRHgmmyzmZgT1oA6WIfuk+lZl2MzOCK1Yh+5T6Vm3n+ub2pFlVgc55qNiD06VKw7+1V3bnjtTARmxUTuW70uKFjLdqBDOSf8KcsZNSrEF5pWwKAsNC7eKQ8/SkZ8A5xVWe/VQQvzH17UATuwGOe9bYHy/h2rkvtDSOMnvXYBcL+FAkcshAkJ9614EuLf97bMsqHlojWOf9YfrVq3uniIKsRQJmiBa6gSF/0e47xv0qpc2MlsSGUj3q0Li3vwBcJh+0icEVYCz2qYJF5bev8AEKRJjfMp9Knjuv4W6VcktYrlS8LD/d71RltmQnimUTdRlefamnDHBH/16qhmQ8VYt54ycOcZoArToFbitfTMGyj9ayrvbvO08VraWMWMf40FIivB+8OetULl9inmr17/AKw1l3b/AC+lA2T2dvCyGe6l2RDsOrVP9puNQUxWUYtbUcGQ8Z+pqjA1unzzAzMOkY4H40txeTXnyk7Ih0jTgUEkySWumkiEfarnvK33VPtUDtLdSb55C59+goSILTywFAD0UL2pXlAHFMjWSdwsalm9BT7i2S2XDuGmP8C9vrQIhLlzj14xU91p89rCksqFFfoTTLZ1hlR3XeqnJX1q1qWsT6q6hwEjT7qL0FAFaNcLUN4Pu1YReOlVr0kAD9aBlUnJpCOPxpTzR0XmgVyTP1ooooApAiiko61YgpO9FGaQCEUhGPxpxIFJ0pDG44pCKccY9qaaAG44oxS8EUn9KADANGBRRx9aQARnmmEA9qcetIaYCUuKTrRQMWg0YpD70AIaMUEUmM0DFoxxSYo6UDDFFJmlxxQAvTNA+tJgUoI7igBelHWjr9aWgQmMn2pQBR9aDigdhAMj2pdtHFKMetIQACnY5ppxTgOaAHUdaSlzTAUUCgCkxSAM80daMZooADSEZpaTv0oGOiO2VB7iuvT7v4VyEQzKnpuFdhECY+TxQA9H7d/epoZ2TvmqzrjkUkcw6Hg9MUAa8UyuOuKn21krIBVyG62jDcikUW8c04L04pEdXHXJqQc+tIpWYzbmjbntzUn4UuKCrEYTPWlCc1IFH4Uqrk0BYaE5pwjzUojANVb3VILLgne/91aAbRN90ZPA9azL3XI4cpDiR/73YVj6jq0t1nc2xP7i1lzytjA4+pp2M3Iu3V9JPJukfcfr0qGOYO2enNU9/wApZuQehPA/KpbdWJ3YIX1bvTJuRawMmH8f6VmEDd/WtHWDkw/jWbQSx+eKcrcVH704c0CJl6cU5SQDTFAxzUq+tAHe2fFnD/uD+VcZcOUvJWBIbeeQa7SzybSIf7A/lXEXP/H5L2+Y0FM2tP8AE81vhLgedH03fxCujs7+DUE3QyBj3U8EVxY06YWv2hUMkPQsvO361DG7QuHiYqw6EHmiwJnogOKnjuCvU5rkdP8AFbJtjuxkf89VHP4iugguEuYw8Tq6HuDQVc142WToeafsrMRyDnkVdhu9ow4yPXvQUTCLH1pRGHBVlDKeMEVKhSRcqc08AA0ho5/UvCMNwGktT5Eh/g/hP+FYUXh+9e4MPkMrDqzfd/Ou/A9qXGR0oTaE4J6mLpfhqCx2vNieUf3hwPoK2gop2zAp4TNS9SkktiEoKaY8ZzS3t/b2CfvXG7sg5JrmNS12e7JVf3MXoDyfqadhNmrf6zDZDap8yQfwg9Pqa5y91Ke+b94xx2UcAVAWySDzTCQapENjdxbPpml96YzhMnP51RuL45IT8TTEW5rtIRgnJ9KhhvvOc54FZzhpAzYJA6nHAqS1zvNIRo3RzbP6YrFIBrVmb/RnyegrKPSgGJ17UZyKMc+tLx/+ugkVBz6U/b+VJGOafigB9vcyW/AOUPVTyKkeCC7GYyIZD1U/dP0qvj/OKQ8YoAjntngba649PeoivNacdyQuyQeYnoaP7NFxzbZY/wBzvQBllcVLbXktoQUPH909KlktXhYq6lW7g1CUx7UAbdpqkVyQGxG/oT1q9gEetckUxV6z1aW2+V8yJ6HqKB3NuW3SYYZc1nT6Uy8x/MPTvWhb3kVyuUIJ7jvVlcHmgZzPllWwQQe9OA5FdHPYx3C/MvP94VmzaVJE+UG9f1oFY24hmFPXArMuf9cxrTQ7IlB6gYrMuuZT9aCiBhkdKqshJq2eRUZHPHFAESw8ZPWnkAHBpSeTUFxcLCm52Cj9TQBJkE1WuLyO3yCdzf3RWddao8mQgKL3OeTVTdn8aCblm4u3nJycD0FV80c0oWgQ6LO9fqK7kqAv4VytppbkLLKRDFkEF+p+grrmAA/CgpHIoA0pHvVmSxeMA7eOxHSqycSnPAzWzD9ot498WLu3/iTuPwoEzKGUPpVq2v5IGBDEe3Y1bWC31EZt22Sd4n4P4VRns3hYqylSOxoINDzILw7h+5m/vL0P1FMberbXAY/3h0NZoZkbjirEd2SMNQBJJbLIPTPeqU1q8WeMj2rRVgfxo5weOPWgoxzyOtdBpI/0CP6mse7RVbgYrb0gf6DH+NBSKl+D5xyO1Ztym4AYrZv1Hmms6VQBQUUkgweal4QUjygcCprXTpbrLH93EOS7cCgnYgLljhetWlsFij827cQx/wB3+I04XcVs4hsIzc3B/wCWhGcfQUj2SwN52pTGac8iFTk/j6UCBLme7BisYvIg/ik7n6mo3igtxtVvPm7v/CPpRNdS3KhABFCOkacCljhCc9aAsRhGepVhCfWnkjnBpGl460AOHtVO9PC1aU7hnj6+tVrxeFoAqUhGacRjtQelAh/+elFLmigDNoxn/wCvRuApN3tVAKefr70Yz0oz7UA+ooAMUhGQaUt7UhPFIBCuaQ9frSntTc0AGKTANL1pMdKAFxSGjHOelKaQDO9IRS8UhHWgYnSijFL3560wA0hIOaWm/WgBDRjNBNJmgoO9FGaM0AJjJ6U7GaTNLQAY5oGOeKTPtSg+1ADuvvQR3ozmjdycikAuOtGKTPtS5oAKUUh60uaBC/zpcUgGaUCmAuMilpBS0hBkUdaSjFAxaMUd6KAE/lQBT44WfoPxqykKxDP6mgRFDAchjxg5rbg1aMqFkPlt79DWJLd7eFHNVXcuTnJoKOyEm4ZBBFIyB+tcraahNaH5WJT+4elblhq0V1hc7JP7ppAXg0kP/TRf1qeG5STBB5qMNnpTJIA53AlG/vCgZoxzFehq5DeDgNWALqSA4lGR/fFXIZwwBBzSGmbysG96kC596yobkp71eS+QDLcCgtMtqnHNNnuorRcyMF9u5rKvddYArCu3/aI5rDuLxiSzsWb1NOwmzVv9cklysf7pMY9zWJPcAAknmoZLgtnsPX/CocM54Bye38R/wpmbYssjddpUH160yNHnbKpn/abpVmO0A+aTk+n+NTnCr0AAoBEEdsqNuY729T0H0pZpUiXLsAKqXWqImUi+Y/3u1ZkkryklmLGgTZPfXYuZFCjCr0PrVfvSBcmpFj/KgncROalVOaVU/KpMUAIBT1703FPHrQB31oP9Ei4/gH8q4e4H+mS8dWNdzZn/AESIf7A/lXD3Df6VKcZ+Y0Ip7GlYWmox4udHu1e4A/eWjnBb6A8NUkV7pmtzmC9T+wtTBwdwIiY+4PK1lLMUYFWII7jtWmdTh1WIQ6rbi9QDCyg7Zk+jd/oaZJFqmh3WkuBcR4RvuSpyjD2NV7a8n0+TdC5X27H6itmyGo6Nbv8A2bKuuaT1exnH7xB/u/1FRJbadryl9MkNvc/x2NwcMD/snvQFzR0zxNBdkRz4gmPc/dP41uA8ZHSvPbiykt3KSRlGXqCKs6br91pZCZ82H+43b6GkUpHfI7RtlSQauw3ynAkGPcVhabrVtqa/unxJjmNuGFXu1Fi72NtcOAQcj1BpyrWNDPJCcqcexp194gktoQI4l8w/xE8D8KVirmtcXENpGXmdUX3Nc9qHil3BS0Xy0/vt1P0HasW5upbuQvM5kc9z2qHPHoKLIm5K8rSOWZi7HqxPJprMMc0wniq1xepHkA7mpkksjqgJJqlJec4A/Gn2Wn3utzmO2iaUj7zDhV9yasTXOmeHpRBCv9u6x0EUQzFGff8AvGgm5A9pMLI3c5EMB+6X4Ln2Heskvlvatu+0a+mX7d4gvVt5WH7q0TlwOwCjgCshLdmOADigZqXevxvpYsLS0WCIgeZI3LOf6VQtF6mpEse5qZYggwBxQBHckC2fHpWUG961rsf6M/0rHAyRkcUCJQwJ6UpIx0pgOf8AGlzxQIfFycVMB0qGDlulXUhLetMCELntUkcDSsFRCzHoAOa3dK8L3F9h2UxRf3m6n6V12n6Lb6emI48t3duSam5SRyOneFJZcPcZjX+6OtdDbaXFbIFjQKoraaAAdMU3ycdqlsuyRh3ulQ3aFZIw3v3FczqPheaAs0IMqdcd69AMOe1MNqDzjpSuJq55Q9qy5BGD3zULQY6/nXp1/oMF6pJTa/8AeHWuV1Xw/NZZYruT+8KpMlpo5kbo2ypII6EVft9daAhZ13r/AHh1qKaAgkYxWfcxEdaok7C1vormPdE4cfXpUwfntXAxyyW8geN2Rh3Wtqx8SE4S5H/bRR/MUFJnSNJxnpWbOSXNWopEmTcjB1PIINVZx8xOaCiIsTxUckgjXczBVHeql5q0cBKx4kf1HSsa4uZbpsyMT7dAKBNmjc6wASsIyf75rNeVpW3OxZvU0wL+NPVCaCRuM9qcqHJqxb2klw4SNC7HoqjmtQWFtpozdN503aCM8D6mgRnWmlz3hOxcIPvO3Cj6mrga104/ugLmYf8ALRh8q/QUy71GW5XZxHEPuxoMKKqdaAJ5LiS5mDyMWOR1rsSPl6dq4tOGHGOa7jjaOM8UDRxBx5reuat2t5JbsGRipHcVWHM7ZH8Rq1JZvGA2DtPRu1AGh9otdRKm4XyJ+08XB/GppJZ7WMC7QXlsek8fUfWsTJQ4xirVrqMtsflbjup6Gggsy2kdwu+3cSJ1x3FUJbdk6c1fH2e6bfC32S49vutTGZwxWVfm9R0NAFGOZ4yPSrcFwkvDHb75pJLZXHHBqpJA6HpxQMfekeYQDxW5owzYJ+Nc2cmuk0Yf8S+P8aGUiK/GJT9Ky735UrWvxiXn0rKvh8g+tIoisZLeAvJOhlcfcj9TV6W2uL2MS38osrX+GMfeP0FUrO7ayLMiKZD0dhkr9KZK0t1IZJXaRj3Y0xFttRS3Qw6fF5CdDIeXb/CqixkkliSe5NOCBaC4ANADxhRSNLTYYprt9sSFz7dvxpbm3S3AXzlkm7qnIH40CY0OX4HOewqzdadPZxI8q7VfpVe3b7PKkhXdtOdp71a1LVptTZd4CovRVpCI4fuiq97/AA1YTgAGobzoPWmMp9fpTW6elPxmmkYHrQK47Bop3PvRQFjNNGTSnrR/n61QBxSEilzzRQAGkPIpRzRSAYelJxTqQjdQAho69acRzSYzSAbSEdKcaO1ADDSGnnrSYB56UAMPNHWlPXpQaBiUjHilIpDzTGN60hpcUUDE60YozRQApGaKAaMUAHalAHpSdxTgOfWkAvFKfekNKKBBx3o4xRRQAZFGQaPwpeKAEBpw796b1paAHDFG4GmE0ZGaAH5xRSAEkDGanjtc8t+VAESoXOAM1ZjtgvLflTyUhHYVXkuS3C8CgSLEkyRD39hVSWdpfYVGcnrQBQMTrS49qMdaUDNAxMZpw9uD60EUCgZoWWsSW+FlzLH+oretrmK6j3RsGH8q5GnwzvbuGjYo1IR2GAQQQCPemLB5bZjO0d1PSs2y11Hwk48tv7/Y/wCFa8bAgEHIPQimMmjPT1qaRvkqFRzUkn+roC5nytyf61nSNknofc9BWjIMk1D5ajAwKBFeKAsd3Iz/ABEcn6DtU6IkYIQfj6025uI7ZMyvjPQdz+FY11q8s3yx5ij9R1P+FAtjTu9Qhtchjvk7ItY11fy3R5OE/ujpVfGee5709UzQK43GaeqZ7U9Y6kCUCGKnFSBacBS4oAKWjFKBnrQAlO60AUAYoA76z/49IvTYP5VxM4/0uX/eNdvZg/ZI/wDcH8q4qf8A4+5f940FvYkNmxiDhSVPeo/LKHmtCwtr1B5unSRzvj57OT+Mew71PFNYapKYWB0u+HBt7jhCfZu340EGfb3UlvIrxuyODkMvBrSlkstbA+3J5VyOl5CMNn/aHeq17pU1nIVkjKHtnoaqlWj7YpiNOQX1kFW5Iv7T+GdeSPqe340ySwiuF3IaitNRkt+A3B6r2NXVaKb5o8RP129jQMxpbOW1cMMqR0Ze1bWl+LHhxHeguvTzV6j60v3hhlrP1GzRQGQYJ7UIEdvBPHdRCWJw6HoRVDVRyuaZ4STbo/8A20apNWGCtD0LMpjz9KhmuEgBLtii8kMMRI61LougWd3YyatrOoLY6ajlAM/vJSOoUVIm7FBJbnVJxBaRPI56KgyTWjcaRpnhaMT+IrvM5GU0+2O6Rvr6VJD4j1DWN9h4M00abZDiTUpxhiPXJqtb2ej+F5mmZjr+snlriY5RW9vWn6ENtkpOteKrQDCeGfDq/wAIO1nHv3NNhv7DQIzb6FbjzCMPfSjLt9B2qlfX95rU3mXUpcD7qDhV+gp0UAQD0oCxE0MlxI0sztJI3JZjkmpViCCpjIsY9/Sqc1wz57Cg0JJZwnTk1DHKZGOasw6Ff3dlJeRW7tbICTJ0HHXHrVK2PJoES3IxayZ9KyAOlbN0MWsn0rHFAmOC5p6xk9qktrd7mQRxoXc8BVGSa7PRfBJO2S9OB18pev4mgErnNaTo9xfzbYoy/q3YfjXeaN4Tt7MLJPieX0x8o/xrYtbKK2jCRRhFHQKKtBOlSy1FIYsIwBjiniJR2p+KqX2pwWI+dsv/AHB1pWG3YsFB19KzbnWbWFti5lPQ7On51i6jrE13ncwih/ug/wA6xptR2jEQz/tEVah3Ic+x2ltew3PCthvQ8GpwBXD2+qgnEg2H+8OlbtnqpUDc3mJ9f61LjYFNG5hc80jwrIpBAI9D0qGK6jnXKt+FSq/pU2LuYWqeE4bgM9viOQ/wnoa4fWdIls3KyRlGHrXrAbJxmqt9Yw30RSaMOp9apOxLR4lLCVJB4qIrXfa14KZN0lr+8X+6eorjrmweByrKVI6g9adybEFrezWbAwuVHcdjUl3qc95kO2FP8KjAqAx460hTmmBHjNKFqQITV6w0ma9BcARwL96aQ4Qfj3oEUVj7etattpARBLdv9miPIB++30FSi4tdO4tF8+bvcSDgf7q/41SlmkncvIxdj1LGgC5JqXlRmGzj+zRd2/jb6mqBySSaUnFJ1pgB60AUUYoAenGPrXcKPlH0FcQnb613I4jX6CkUjg2bFw2f7xrXtheWse+323cJGXgbqPwrDkOLl/8AeP8AOr1pfPCQVYg+opEs0EFrqWRA32e47wSnHPsapz2kkDkOhQjsRWi0lnqqgXKbJe00fB/GpHNzZRbbhRf2g6SD7y0yDGOV9qnS7ONr/MBVt7WC5UvbSBx/dP3hVCW3aNjkGgC2MMMrzRkEEGqKSMhyOKvWtzFI2JRj3pFFS6jVOQK3tFH/ABLo/qf51j3+0PgHI9a2tDwdOj+p/nTKRDfj98fpWbcxGRQB61q6gP3xHtVCUhFyaCikLcL15pGYCklm3Vag0p5IvtFxItpaj/lpJ3+g70CbKW5nYKgLMeijqastaQ2Ch9QkIfqLaM5c/X0pyX7O5t9GgZSeGuXGXP0/uioxZ2unMWuG+2XROSgPAPuaBXHLLealGUiUWVkOoXgY9z3qNjb2y7IQZG7ysP5Uk9zNet85wg6IvAFOSAdTQFiHDSn0qVIgnapcc01mAoAeORVa9x8o689asIxZaiuYWkwFUnHOBQBSpcZxQQRn1o6YPSgVybHsaKXf7migVzGFGD9aBxR2pgFFLzR9aLgBNB60dKOKQXEzR3oo9c0AIfrxR2opDQMDjFNI4pxpuTQAcfWkxRmkzxzTATHvxR3pSc00mkMMUhoo+tAwxSdcmjHrSc0DFAoxj6UYz1pD1oAMUYoINL/KgAxSj5aQUtAhaBSUoFABSmiigEFFJQaBB39qXPNJT0jLngZNAxuf8mpYrdpO2B61YitFQbnOaJLxVGEGfegQ9Y0gXJ61DLdcfIOKgeRpDljmkFAwYsx55NH8qBQOaBhjNKKMUCgBcUuKBzzS0CDGO9JjNKAeaXFACbeKQ807FG3PWgBMDHSrNpfzWR/dtlf7jdKgAzRjPrQFzpbDWobvCt+6kP8AC3Q/Q1pyONlcQBx0q5HqdxHHs8zI7Z5xSC5sXFzHbgtI4Ue9Y93rhb5bcbR/fbk/lVSZTM5Z2Z296b5KimK5E7NK252Lse5oC96nEYHal2gHpQLciCVMqc0oxTxQAgxmngUYzRQAdqBS4ooAMZ70AdaBS+tACgGlxTeuKd1zTA7+yH+iRf7o/lXD3AP2uX/eNd1Zr/osf+4P5Vw8/wDx+S8/xH+dItjo5WjYEHB9RWqNSt9TiEOqW4vYxwJR8sqfRu/41UbTZWgEyDfH3K84+tVSjKTQQdDbwXthAf7OmXW9NHJs7jiaMe3/ANb8qjhjsNZ3C0cwXA+9aXHDA+x71kW13JbuHRmRgeGBwRWw11aa2FGoRYnH3buHiQfX1pkso3OmyW7EFSG9D1qBWaM8jp61tOl1aKFkcX9v/DKPvge9Me3huVyOtIEypaXamRVkbapPJxU+riHenkOHQjOaqXGnvEcr8y1VDkHB4NNDOx8Mf8gv/gZpdXwSlL4X/wCQWe/zml1YAsnHrQy0znNU4t/xFQaaujoDLqUM126HKQA4T8ataom6Dgd6zI7Qty3FShMv6j4ju9TjFvCq2lmvC28A2rj39aqQ2wXrUoRIl7AVBLc4zt6UxFoska8nFR/aHmcJGpYk4AHJNT2+jObb7bqNwmmWHXz5+r+yL1Y1Z03Ub3UmaDwjp5gj+6+r3o+bHfb2X8OaAuSy6JBo9p9q1y7WyyMx2indPIfp2H1rBWZJxuQFVPQHrWvLomi6Qzy39zL4h1VuWYufLU/XvWVJuuJCyxrGp6KgwBQO5pT+KtSn0mLTBKIbONdpSMYLj/aNULVDknrUkNkTgtWzpfh64vmzGhRP+ejdP/r0hoybpP8ARZPpU+h+DLzVCskqm2t+u5x8zfQV3mm+GrexAZlE0v8AecfyFa6xAUXHYydJ8O2ukx7YI8N3kPLH8a1Ui2jpUoSl4QEngepNIoaE/D602eWO2QtI4QevrVO61ZY8iEb2/vdhWDf6gFJaaQsx6Dv+FUot7kOVjQvtcdwVtx5af3v4q5m61BVY7T5jnqagur2S5OB+7Qfwjv8AWnWOlTX7fukyg6u3Cj8a0SSMXPuVZJHnOXOR6dhU8enu672AjT+83Ga0khtrOTy4F+23I6t/AtNlG9/3refN2RPurSuYud9jHniCng5HrTYrmS2PynjuD0q/cwsW+fG70HaqkkPXjmhApF+z1hWIDExuO+eK3bXVQcCTjP8AEK44w89Knt7uS34zuUdjUuJrGdtDu0kDKCDkHuKmDZ+tcxYanhgUbB/uGugtdQilG1vkb36VDVjdSTJ2j3cYrM1Pw/a6mh82PDdnXgitraD0ORQYxzxSL3PLdZ8HXFkWeIGaL1Xr+NYEelz3M3lQxNJJ/dUV7c0QIxisrUtAgvIZFQtbM/3nh4J+vrQmJx7HmgtrPSf+Pki9uh/ywjP7tD/tN3+gqpeajPqDDzmwi8LGvyoo9hWlrnhW80YlyvnW+f8AWoP5jtWL3qzO1hcc0p60mDnrRQAAZox60nU0vXvQAUuM1JBbyXDhI1LH2q75dtpvMxE8w/5Zr90fWgCOz06S4HmN+7iHJdq68DKLjkYGK4m81Ka8yGO1Oyr0Fdraj/Rof9xefwFA0cG0f+kvn+8c/nVs2MkQDFTgjIPY1Ew/0l8j+I/zrYtUu7KPfAFvbU8tCRkr+H+FITZlgMh7irdpqcts3B47g9KupBaaopNs/ly94JOD+FUp7N7diGQg+hoI3Lnl2142+M/Zrg85XofwpreZGNk6Bv8AaHes8Eo3pVqG8J4fmi4rWEls1kGYz+FU5I2iJDDBrTG0/d4NDlZFKyL+NAzILkj+prp9DOdOj+p/nXPXMKxtheldFofGmx+mT/OmXEj1Afvj9Kyr5sQ/jWtqWPOPuKyL/wD1I+tBZHYzx27Fvs5urknEcZHyj3I71YubRp5Bcazcnd1W3Q8genoKpW97Laq4iYIW6sBz+dRbWkYliST3Pegmxbn1Nmj8m1jFrB02p1P1NVo4MnJp6RhevWnlse1A7WHIoWkeYL35qPe0rhI1LsegUZJp1zY/ZF/fyqsx6QqcsPr6UBcYZixqaazmhjWSSJkR/uswxmq8TBJVYjcAQSvrWnrOuyayY1MawxRj5UBzQSV4B8nrUN3K0RVkJVgeoqaHharagfujtmgY77TDeDE48uX/AJ6oOD9RUU9q8GGOHQ9HXkGqmamhupIM7G+U9VPIP4UEkmfpRVj7cP8An3i/WigDA9aB9KX1/wAaKAEz/k0ZpfwpMZpAHU0UpH4dqT8KYB17UH36UZ9RR17UAHSmk0p6c00nNAxDjmkPP0oNJ2NMA70hPFITmkJpDFPNNJ5oY5+lFAwooNJTAO9L+tIKXtSGFJS4oPNACYo+tFHegBcc0tJ9KXpRcQD6Ug5petHTtigQufyozSGg0DE6UuMn1qSKFpTwOPWrOIrUZPzNQBHFaFhlzgfrUrTpAMKMn2qCS6aQ4HAqCmBJLK8pOScUzqaMUvekAvWlHJpMU4UAGM0vSjFGKBhR3pcUAfhQAAZp3rRig0AGM0UAZp2KBCUuKWgdelAgop2KMdaQhMUoOOlGKUdqADvQDzR39qMfhTAQ8+1Az6UtFACinDp0pBThz7CgBccUuOvpR0pKAF9KWgCjBI9KAAc9uKUcUUAUAGKcKQDPWlxTA9Dsxi2j/wB0fyrhph/pkv8Avn+dd3ZcW0Xf5B/KuFuB/ps3++f50imbGmWt0oE2mXKmb+OznOA/+6anMunanMbe7ibSNQ6FJBhWNYsU7QsMHGK2Y9Zh1GBbfUoEvYRwC/Dp/ut1FBDKeo6Dc2Byyb4+zpyKoAtGfSuntLa7sELaRc/2nZ/xWNwf3qj/AGT3qBo9P1pmEANneDh7aUbSD9KBXM601R4SBng9R2NaKyxz4IIDH04rKvNNmtHIZSPQ9jVdJ3iPGQaLgby5JIIznuKo6hbiMhgOTT9N1OITJ9oVmjz82084q94gNnshNpIZFPJ3DlfammI0vC4zpbD/AGz/AEp2rA/IcUeFTnTX/wB8/wBKl1Ycpn3oZojDucbDnpmsye5VOAKv6o2234457Utq2iaLpkN9qTNf3k2fJ0+Hr1wN1SgZR0/Rr7W2LRJthXl5pDtRR7mpYryzs7z7HoNt/wAJFq46zsv+jQn19/qatX1lqOvwJP4guBoeijmLTLbiSQe4/wAahl15LS1+w6PbLplkOCI/vv7s1BJJJo9tBci+8T3ra1qfa0Q/uo/b0pmoeILvUlEKYtrUDCwQjaoFZscTSNnk+571dihWMdMUx2IYrPcMn8qtLAqjsMUj3CRDGQTVOS5eTvgUDOo8J2cF7eSmVQ6xAEA9Mmu6jiQABRwOgFcT4FhkSO6keNlRyu1mGN3XpXWJIyHIOKRaLvle1L5ffFNhug3DjB9RVnaCMjke1IZCFyelZesadeSgyQP5qj/liTj8q2ihz6UgBHSmnYGrnnF7qc8bNH5fkuOCD1FZTOzsSxJJ7mvUtQ0i11WPbcRgt2ccMPxri9Z8K3GnFnhBuYP7yj5h9RWqkmYSi0ZumtZxyF7tXkA+7Gvc+9Wb3WJL0CNR9nth0ij4rKJIpyyYNM52tTTj8yWMKii2t/bq341PGgWM+UoRB1kbp/8AXqvFdRCMNITK3aPt+NNkuXumHmNgdAqj+QqDNjpHUsFiVpnbocdfoKmh03dKBOTJKekEXLfie1WobM20O+Y/Y4j1HWV/8Kqz60tshitIxAh/i/ib6mqSF6Fm4s7O1Qm6Cq2MLBF2+prnnA3HAwKJbhpGJJJJ65p1vby3kwjhjaRz0VRT2LjFjV+U8VtaRaXuoEeWn7sdZH4Uf41q6T4QSICS9Ikfr5Sn5R9T3ro1RUUKqhVHQAcCs5S7HXCm92U7OyNpCELmRj1J6VORxUxX1pCvNZG6ICtGzJpl7fQWKZlcA9lHJNc7fa5PdfLH+4j9AeT+NUk2Js0tVv7e3ieI4kdgRs/xryO/iWK6lVeFDHFds+cHkmuL1Lm8m/3zV2sQyoaAM0verNjZm9m8sOFOM89/p60iStsJOACT2xVxbJLZfMu38oHkRj7zf4UT3osGaK3iMcg4Mko+b8B2rMd2kcs7FmPUk0AX7jVWKGK3UW8PTC/eP1NUdx+tNBpc5oAdng16Faj/AEeD/cX+VeeCvRLc4ghH+wv8qQ0cXcQvDcyKwKsGPX61YtbyS2YFWII7iuqurOG8TbKgb0PcfjWJd6DJCS0J81P7v8QoBocZrTVMfaUMM/a4h4bPuO9Tym4tIf8ASVF/adriL7y/UViBWjb0IPINXLXUprRtyOV/kaZm0SSWcdwvmW7h19AeRVGSBojyPpWoGtrtjIh+x3B/iQfI31FRylgdk6DP95T8ppCRnLMyH29K0bB4Ll9s0nljHWqs9oCMpx7GqbhozyMUFD71lErAHcoJwfWt/Qj/AMS2Pvyf51yzNniuo0PH9nR/U0ykN1A5nP0FZd6hkjAHrWlqJ/0g9+BVGZwFzQWU0tgv3utOYhfamyXGeFp1pZT6g5ES5UfecnCr9TQK5E83FTx2DGIT3UotLY9Hf7zf7q96c95Z6Y4jtVGo3vTzCMxqfYd6VtLd2F3rVwyk/dizl29gO1ArjY72a4Y22kQNEp4aduZG+p/hFNksrewVhJL9puj12n5V+p71JNqjNEYLSL7Lb/3V+831NQRWhIy3AoERKC545qzHAFxnmpUjVBwKdQVYTp24qjqByFq+fpVDUiPl55zQDKNB56cUhINA9aCR+D6Cilx7UUrgUADSgGgc0fpTEIOTyKMUuetIOtABk0YNLnNITQAn1H50dqTNBNMYh96TrQTk0h5pAB+lNPPWlPNNJ/KmAEUmfag8/hSYoKDNHFJiikMU4P0pBRj86KAFAowKQdaWgAxQRnNL0ppoAKBzRRQAvJxQc4PHNGfWlPSgQznNKMmgDPvViK2J5bgUDIVRnIABq3Haqi7pSPpQ0yQDCAE1XeRpD8xzQInlu8DEYwPWqxJY88mkpetABil7Ug5pSBQMM/5NKAKQLTsA0CF4NLTcAD1pRg0DFpcAmlGMZpcCgQAClxRRigYdfpS4z7UYzS4oEAGMUvagcUUCE5xS4pc8DigcGkIUZoIP0pR1opgJzRg4pRS/higBMGgCnUD6UAJQB2paKADHtSgZ96Bj/JoFADu1HFHYdqMZoAAR60tJj1pQM0wDr0pwxjBptOAx1pALS9qQ4pcZBpgei2n/AB7Rf7g/lXDXA/0ybt85rurIYto/9wfyrhrj/j9m/wB8/wA6RTLI06Sa3M6KWjHDMOcfX0qqyOh6H61r6ZaThluNH1D7PfgYe0uMeXN7A9PwNW/tVjf3JtNRg/4R/Vf7kwPkSn2P8P8AKgzbMS2u5bd1ZWKkdCD0rb/tC01pFTUoi0o4W6i+WVfx7/jVTU9BuNNk2yxGPPIPVW9we9ZxVo25yDQBv3Ed9YQZZl1Ox/hnT76/7wqjNYJcLujPWorTUZYDgMcHgj1q4siTkMjeW/tTEY89pJA3K4pnmucAnIHrW7JKQu2ZMj+8tZl7FEgDxNkE4IpDOq8JZbTX/wB8/wAqsauMbO/Bqt4RP/Esb03ntVvVhxH+NNs0RzWqj/R+v8VQabraaREWt7KE3vIF1INxUewq1qsZNscDPzVmR2DE5fgUkDGT3FxqE7SzyPNK3VmOamitAOW59qn2Rwr2FV5bouwSIEseAB1NAiaSVIByRUUH2nUpxDaxPLI3RUGSa0V8Ow6bai+166Gn2/URHmV/oKbZanrPihHs/ClgNI0wcSahMdpI7ksf6UXESXVtpPhVQ+uXP2m8Iyum2jAtn/bbtWWbo3UhuvsyWgY7khXkKO3XrWla6XoXhYlol/4SHVzy93cA+Sjf7I/i+prPljuL2ZpHXDMckgYH4CkhnbeGdfutaSYXOw+TtVCi7ePf8q3BjcBkZPQZrl/BlubZbrJySV7fWo/Gk0kMlk8bsjAthlOD2oKOxH6VPDM0Z4PHp2rhtJ8ZyRBY71fMXp5qj5h9fWuttb6C9i8y3kWRT6Hp9adhpmzHKsoAzg04qR2rMDEGrMV8VADcipGiyyke1RMCfaplZZRlTn2prKQTSGc5rHhW31HdIn7if+8o4P1FcXqek3elSFZ4yF7OOVP416mckdKZJAkyMkiK6N1VhkGqUmiJU09jyNXYH0rSsNV+wqWSFWnPSRudo9hXR6v4Gjm3SWLCJ+vlP90/Q9q4+7sriwm8q4iaJx2Ydfp61qmmc0qbWjJrq/luXLu5YnuarZdyAAST0HrWxpPhS+1Mh2X7PD/z0lHX6Cu10rw7Z6SAY08ybvK/Lfh6UOSRcaVzkdI8HXV5iS5zbRHnb/Gf8K7Ow0u302Hy4IxH6nufqavYwOKaePesm7nRGCjsNC4/+vS7BijAxknAHc9KydQ8SRwZS2AmfpvP3R/jSsU9DSneK2jLyuI0HdjXP6h4lL5S0Gwf89GHJ+grKurqa9k3zSGRvfoPwqDHtVqJNxXZpHLOxZj1ZjkmmkDr0pcZqGeeOBcu4BPbvVEhIMLXFX/N5Nj+8a7N5N30rjL/AJvJv981Imyt3oyRyDgjvRig0iS6morcKIr6Pz06CUcSL+PeobjSG2GW1b7VB3K/eX6iqxqSC4ktpA8TlHHcUAVSDSc1sfaLXURi5QQTH/ltGOD9RVK802a0G8gSRHpKnKmgCoSRWvpviaezAjmHnxDgZPzAVj+3Sk5pWBHoFjqlvfpuhcE91PUfhVwHivM45nhcPGxRh0IrodM8VsgCXa7h08xev4igdzpLrT4bxfnXa3Zx1rDvtKmtMsV3p/fX+tb1tdx3UYeNw6noRVgNn8etMdrnFZZeh5qxFeNja3I9O1bl7okU+WhIik9P4T/hWBdWktpIVlQqex7H6UiWi0CCPlP4GmyRCUEEVSWRlPtV20lWQ4c8e9MVjKuE8uRl7V0eg/8AHgo9zXO3h/fuO2a6HQP+Qevfk0FIbqPNyfoKy798IK09S/4+T9BWTqXCrn1pjYWZs4YmuLxmZVOFhTq5/oKt+Tf67DukKaZpS9M/KuP5sao2F7b2YaR7Vbm5B+QyH5F/DuaLm6utWl3TyGQjoOir9B2pEl0ahaaUvl6XFvlxg3cwyx/3R2qj5ct1IZJWZ3bqzHmrENiF5PJqyIwB0oHYiitVQdKlAABpSAKRiADmgoZ096ax59KrXOoRwcZ3N6Csq4vpbg4J2r/dFAmzRudSSPIjw7foKznmeU7mOTUI4pw5oJH7s0uStIiF2woLN6AVorYxWihrtsN2hU/N+PpQBU3e4/OitD7Xb/8APon50UgujAxR60Uh6VQgzmikJNG6gB1NJoJOaCaQxKTOPbFHOOaQ80wEzRR1FJQAE0mfxpD1o/SgYmc+xozQaCKQxDRRikoGL1oyaOlFAC0ZpM0GgQGj+dJnNIeaBi0detJ7U9EaQ8CgBKmjt2frwPepUiWIZOCfemSXJHC9PWgRLiOAZ4JqKS5ZuM4FQFyT6+9AoGLmjqKBQRQAU4HrSetAzjpQAuaXNIPpS0AAPanZpF6elL17UCAn86VetJjPtTgKAHYzmlpAKXPWgBe9Aoo6j2oAWjrS0uOKBCYpaO3pRQADmlpBzSjmgQUtFFAxaOaBSE+1AhQaKQdKDmgAzjFKDmkpPrQA/OaXP/66ZmlFAD8k0pNNxxR+NAC5604U3rxTqAAc9OKcOlIDS9aAFxQOlA5NW7Gxe+mCqPlHLN2AoA76zGLWL/cH8q4S64vpv98/zrvrdQIIwOgUYrgbogX83++f50FMcJCpFbEGuLc2wtNSgTUbPoI5vvL7q3UVAmjtd2QurVluYR98xnJjPow6is+SFo+eo9aCDqNPiurGApo866vp3VtIvziRR/0zao0trDWmdbIvBdr/AKzTrsbZUPfH94VzsF08LgqxUj0Nbf8AadrrMaR6nGZWT/V3UZ2zR/Ru/wBDQKxTutNeFmGCCOoPUVU8x4Tjmtydrq2UNLINUtP4bpBiVR6Ov9ahe0hvU+QhvcGgCtY6gPOQM3y553U3XkVZUZCpDDOVqtdaZNBlgCyeoqmd3Q0xnbeER/xLG/3zVrVzjyh7Gq3hIY0tu/zmp9YOPL7daGXEzZdojy3TPesq6vFTIXBqzqMmLY4PGas6XfaDoWmw3c8b6rrEjER2QXKqc8ZHc1ISKeneG73Vk+0zstlYjlribgY9h3qa21iFLs6d4QsG1XUQMPfSL8ie/PAFWtT0m+1nZe+Mb9tNsTzFpNsf3rjsCP4fx/Sq1z4maKz/ALP0a2TR9NHHlw/ff3ZupNBJIfD+m6VdfbfE943iDV+v2NGzEh9GPf8AzxUeqeILzWgIMLbWa8JawDagH4dazra1LctxnnnvWhHGseMAUWGMt7MAZPWrbKqL2FRSXSRDGQTVOW4aQnJ49KoZ0vheRZPtO3tt/rVTxuP+PT6t/SpvB3K3RHqo/nUXjfn7GO2W/pU9Q6HOpHuHXHvUsM9zp0okgkaJx3XoauaQ1zFL5ltYpqBVTvt3XcGXv7/lWnbw6Vr7MlhKdPvf4tPvG4z6Kx/ka2SM27E+leOI5SsN+vkyH/lqv3T9fSunjkWZA6MGQ8hgeDXnmp6HLaSFJomhf+6w6/T1qDT9VvdCk/cOTGTzE/Kn/CpcSlI9MWRo2yDg1dhvw3Eox71yuleKrPU8I5+zXB/gc8H6Gtgnnis2jRM2wgcblII9RSFDn0rJhu5IG+Vvw7GtO31CKfCviNv0NSaXH7DTXgRypZFbByCwzirJjz0NNKHmkMix0o21JsJ7VDeX1tpybp3Ck9FHJP4VSAftLcAVQ1DV7bT8gt5sv/PNT/P0rH1LxJPdbkgzBEeOD8x/HtWOATnuatRIcuxbv9Wn1BiHbbH2jXp/9eqZH5Uv4YqN5AvXpVoi4pOO1QyTJEMuwUepqnd6ukZIjw7foKyJrl53y7ZP8qCbmncarnIi49WNZ0rl5VLHJz1zWr4S0BfEmqG3luY7O3jTzJZpGA2qPTPeqWtR2kGtXENhIZrNJNscmc7gO+aRN7l5q5G8/wCPub/eNdcTnvXIXn/H3L/vGpKIqT8KX8aMZpCGkfSjFKeO9JQAlTWt7NZk+W3ynqjcqfwqE5NJQBeaGz1H/V4tLg/wN9xvp6VnXVnLaSbZVK/yP0NBq1DqTonlzATw/wBx+30oEZpHakFaklhFdAvZvk94W+8Pp61nyRNE5DAqR1BGKBklrfT2EgeFynqOx/Cuo0rxVFcER3GIJOmf4T/hXIYxxTGBoGtD1FJFbpgjtSyRpOmx0DoeoavO9N12600gKxki/uP/AErsdL8Q22ogBW8uX/nm3WkUmVr7w23L2p3D/nmx/kaw5kkt3KOrRuP4SMGu6V+aju7GDUI9s8Yb0buPoaYrHAscnJrp/DwzYL/vGqWo+GZrfLwfv4x2/iH4d61NBhKWChgVO49RigEitqYxcn3ArJ1JC6KFBJz2rc1Rf9KP0FUyvP8AjTKsZdtprEgycD0rQjhVBwMVKFFGcUhDQuDSHGBSSyrGpLEAeprHu9azlYf++zQDZpXN3FbDLsAfQdax7vU5J8hfkT26mqLyNIxZmJY9SaQHvSJuOJ5o/SgA1bs9Nmuydi4UdXPCj8aYiqFq9b6czoJJWEEX95up+g71Y/0Ww/1eLmb++R8g+g71Wmme4fdIxY+/agCwb2O2QpaLs4wZW++f8Kp8uSScknknvQFzTgOfekBL5Qop+aKZBjZ60hNGc96TpTKAn2oyaKDQAZ4pMn0oPXmj8KQxC2TjvRk88UvPWkNADSc0hJ5p3UU31oAaTnFBPNGc9qO+aZQH6UnfpTqbz60AGT+NGM0UetIYdKKTNBNAhB+lB5pDR17UAHWgKW6c1LHb5+9xUu5IR7+lAxsdr3f8qe86xjCgGoXnZ+BwPSo+tAD2lZycmmBsmgDNLQAv4UZxQKUCgYufbijdSgZ96OvagAB/nSg0YGKWgBM5pck9qDyaPwoAUNmlz+VApc/lQIPpTh2pKX0oEOooB4o7c0CFpf60gp1AwApaSlHNAgIBo7etGaO1AB1pentSUdfagBc8UbsUn0pc+1AhS1G7jkUntR+FAAGozntRilJ74oGLn2pNx5pcmkzQITcRTgab1+lOHPNADhyKWkwBSk9aACjr7UmaX8aYC1JHG0rhEUs56KByavWeivJELi5cWlr/AM9JOrfQd6lk1yHT1MemRbD0M8nLn6elICzBoUVnGJtTmEK9RCp+dv8ACq+oa7vj8izjFtbDsOrfWsaa4luJC8js7HuxzTQ1AHp+nHNjbnuY16/SuFvPl1CfIyPMP867rTObC2I5/dr/ACrjtc024sbySV0JhdiVdeR9DSK6F210y3uJVu9FvW0fVB/AzfupfbPb6HIqZ9Ut5LgWfiG0Oh6geFu41zBL7kDp9RxXPxylMEVt2muebbfZL6FL6zP/ACym5x/unqDTIsM1TQZ9P2u6h4X5SeI7o3HqCKzCGjbng1vWVhd6arv4buxdWrcy6Re4YH6ev4YNMjk03WpWhiRtJ1IcNYXRwrH/AGGP8jQBQs9Rkt2BViPpWtHNDeANjypP7yf1rLudLlt5WRo2SReqMMGoFkeBscg+lMDoknMY2zLuH94Cs/VbOHaJY8ZJxx3qfR9Tg+0xrdgtDn5gPSjWhEJX8jIiLfL9KANrwnxpZ4/jNS6zk+Xx65pvhMZ0pv8Arof6VNrC8J+ND2Licxqg2W3P94VHpviWXRYX+x28Ed22f9MKbpFHopPSrepW7z25VBk7hWfHpQU5lIb2HSpQ2VJJbi/naWR3mkc/NI5yT+NXbe1CAE8t3qZgkK84UDtVWfUAOE47UyS3JMkIyTioYpbjUbhbe0heaV+AkYyTTzpaWNut7rlydOtW+ZIiMzzf7q9h7mpLHUdY8RxvZ+GrP+xtMPEl2xw7j1aT+gpXEW5rTSPDAEniG+MtzjI0yxYNJn/bbotZb6lbXc/2mKy+z27NlbUuTgehPWrkGjaH4ZBb/kN6l/FLL/qkPsO9UZ2kvJnkKjcx6KMAfhQgO50LxD/byyKllb2EFsFVIoAe+cknuayPG+M2fflv6VJ4LgaBLrdxuK/1pnjcj/Qvq39KaK6GHa3cto6vE7RuDwynBrWl1Kw19RHrFvmXot7D8sq/X1rGSBnTKjIHWo2VlJrZGbR0om1PRbXEoXxJofZhzLEP5j/PSmrptlrcBm0m4E69Wt5OJE/xrG0/VrnTZQ8MjRnuOx+orSdbDWZhcRMdI1McieDhHPuKZGxj3+mPCzAoVIPII5FT6X4nvNLIjkJuIBxsc8j6GtW51C7h/c6vbiQ9FvIuQ31rOubCG6G6Ngc+nepaLTOt0zXLTVUHkyYk7xNww/xrRDV5dNYzWrh0LKRyGXqK29I8aS2+Ir9TIg481R8w+vrUNGikegW2oSwcA7l/umrx1m1SNmkJjx2xmsG0vIb+ESwSrJGe61Hfjbbv71FjRMm1Lxa7Ex2ieWP+ej8n8BWA87yuXkZnc9WY5Jpkx5pFI+lUhN9yQGlL8Hiqt1fw2i/O4z/dHWsttRu9TmEFrGxLHAVBljVEOxoXmqRWvDHc390daz4I9R8Rz+TaQM477eFUerMeBVq60jTvDEQn8Q3J+0Ebl023bMz/AO8f4RVVpdc8YWhjjWPw54cHYEorD3PVz+lK5F7jLvUNF8LN5YK6/qw48uMn7NE3uern2HFZDT3VxNJNdpsmkO4qE2AZ9B2FbVtLpnhxCmj23n3AGGvrlcn/AICvaqJiuL+ZpZGZ3blnfvQgKmckZq1bQM7A4wPWrkNlHFyfmOO9LJPGgwTz6DrTHYsiuRvObubP98112K5G7/4/Js/3zUjZH39KTFLzk0mc0iQxmigmkxQMTtSH0pTzSEd6AGHmkPFOI61esNEuL6MzErbWi/euJuFH09T9KAM8EowKkhh0I61upaF7YPqxW3jI+Rj/AK1voPT61H/aVppWV06Pzpx1u51yR/ur2rKnmlupWkmdpHY8sxyaAJrzSHjjM0DC5g/vp1X6jtWawq5b3U1nJ5kLsje3erby2mpZ81RaXB/5aIPkb6jtQBjGmglTkZBHer15ps1mRvXMZ6OvKn8apsvrQBt6V4suLMqk48+IcZ/iH+NdfYavb6im6GQN6r0YfhXmmOelPhmkt5BJE7I4P3gcGgq56qGoIz2rkNK8YMgEd4uR081Ov4iuqt7qO5hEkbB0PRlNIozNTH+lH6CqZ4q5qbZuD9Kxb7VoLLKlvMk/urTFexdLgDrj3rMvNcihJWPEr+x4FY95qc97kM21P7i9KqY7UCbJ7m9lumzIxPoo6Cogc0gU1LHC0jBVUsTwABkmgkZjOBVq0spbuQJEhdj/AHaux6VFZqHv5PLPaBDlz9fSrMOrwbGt/KNtC3Roj8w+vrSARbOz04ZuWFzOP+WKH5R9TUF1qMt0AvEcQ6RIMKKW409o08yNhNCejr/WqwHNMBAM0u3qafj8KULQAzA79KcB7U7Bo20gJMUU7Z9fzopgYPPemnmnYoIzTAbzz2o60pB9eaKQCDmk5pwHHWjHrQAgNJjmlxRjNADc0hpxFNIzmgBvejNKaTPrQMP1pDS0lAxD9KMUZzRmgYdKOtAXNSbAOe9Ahixlj7VMNkfPeo2l9KjLE9aYErzkjA6VGeaTH4UY/KkMKXpRt96UUAGaM5HrRjPfilxzntQMT6c0oPtQB37UoFABz+FKPcZFGM0AZzQAuOKXrRj8KXrQK4hoBopRQFxccUozQKM0CFUHNKKaPWnCgB1L1pBS0ALjmjik9aKAHD0opM0CgQtBNJyc0tABRmkxTsY4oAToKXnrSbaUCgAzil5oAxQB+VAheaMmjGe9GKAExSj3oxijqKBhS/pQOacKBCjJ9qKBSZ4NAD7eIzSpGGCFjjLcCtaR7TQnKrF9qvV/jlGEX6DvWL+FX4dSDxiK8i+0RDgN0dfoaAKt5fT30pknkMje/QfQVB3rSk0gTI0lk/2hAMlOjr9R3rMZSpwRjHagB2aN2QaafrTSaAPUdGkV9MtiCCPLXkH2q6Y1dCrAMp6gjg15bp2tXWlSBoJML3jPKn8K7bRvF1rqW2KYi2nPZj8rfQ0rFDdS8JxTZksyInPPln7p+npXOT2k1pL5c0Zjcdj3+leipgH2ouLOC9i8ueNZEPY9vcHtTHY89t7p4GDBipB4I7VsyX9nrsIg1aAXGOFuE4lT8e/41JqvhRoN0lqTKnXyz94fT1rnWVonIIKsOx4xQRY6H7PfWNuFEv8AbOnL9yQf6+EehHXFNMMN4uG5B6MOorMsdWltJAVcqR/EpraTULbUADMojl/56x8Z+opi2Mq70qS2+ZRvT1FQedJt2sSQOxrokDQgAkSRnuKz9Ut4l2si7c9cUDOi8IfNpLHH/LQ/0qbV1/1ffrTPBq50dh/01P8ASrGsj/VenNDLRjTfIhY4ArHu78DIQfjWjq7bbM+uRzVex1Hw/olgt1exyapqjkiOwUEID23etSKRVsNFvdZVphtgtE5ku7g7YkH1PX8KW21ONL37H4TtH1rVBw+pzpiKL3RTx+Jq/faPqGvxx3/i+8OlaUObfSbf5WYdvl7fU8/SobrxN5Vp9g0e2TSdOAwEi++/uzUiRg8O2GmXTXviK9bXNWb5jAGJRT/tHvRf6/d6kghXFtajhbeEbVAqlbWMtyc4IX+8e9bFrYRwAcZb1NOwFO105n5fgelXxarGMAYqzjA4FG3g0yy/4fTYJ/qKzvHOR9h78t/StXRV2rJ9RWT47kAFh9X/AKUDexQ0iO6klzZxLcTIN3kOceYO4FakEOm6/KYIWbTdQBw9jd5U5/2TXP21w0DK8bFWXkFeCK6D+17LX4hDrNsLhl4W5j+WZPx71qjCVzL1TQLnTpCssbKe2R1+hrNJaJvQ+ldvDFqOnW5FtKPE2kDrBJxcxD29aoT6RZ65C8+lSmUr/rLZ+Joj6EVRKZj2etuieVL88Z6q3Iqf7Okh32zbD/dzxWbdadJbsQVPHt0qOGaSBshqks1ElIISRcH1qG90uKVC6Da3t0NOhvIrgASjB9RW/cafZnSRNaTFyqjerHn8qA2MbwFuj1uaME7TESV7E5HNdpqabbR/wrk/BEYHiGTn/li38xXYaqv+hSfh/Os5bmsdjlZzgMegrAu9bklkMVv1PGRySfaty9H7qX2BrC8K6tdaddMNPso7u/l+WJ3XcU+gqUEtEa9n4QaK3Goa7dLpVmecynMr/RafF4gur8vp3gzTjaRAYl1Gb/WEdyWPCior3R44rn7Z4q1B9QvTyNPgfJHszdFHsKr3uvT30AtYY0s7Ffu2luNq/j/eP1pmW46207SdAlaaZhr+rE5aWUkwI3rzy5qK/vrvWZg9xIZSPuqOFQegHQU2CzL8vwPSrXyQL2WmkVYhhsFUhnwx9KdNJHAuWIA9PWoLnUtvCfnVCdpN2ZAwYjPzDHFUBNJdPOSEGwfqagKbWHPOa2PCdjpV/ezHWNSGnWUUe9mAJeQ5xtUDPNU9euNNm1VhpEc0diuApuD87HucdvpSuK5fxxXIXn/H5N/vmuw6dK469P8Apk3++aRTIc0HvTc5pe1IQoo7UhPODSqrOwVQWYnAAGSaYCHmp7OwuNSmEVtC00nU7eg9ye1aSaJDp8azatMYMjK2kXMr/X+7Ve81ySaE21rGLGz/AOeUXVvdj1NAicxafon+uK6lej/lmp/cofc/xfyrO1DVLrVJA9xIWC8Kg4VB6AdBVb1pMCgAI9OBSYpcZoxxSGN5pDxmnkZppHNAE1rqU1nlVIeI8NG4yp/Cp2s7bUsm2b7PP3hc8H6GqBWmnIPHFACTW0ltIUkUow7GosYrTh1EtGIrlfPiHQn7y/Q0k2mrKhktX85O6/xL9aAMwnBq1Y6nc6aSYJCueoPQ/hULIVJyMeuaYVwKALd5rV5e53ybc9QgxmqGMmnY5pQuaBjacsZPQVdsNIn1ByIoywH3nPCr9TWmG0/RxhQNQuh/Ef8AVKf/AGagRTstDkuI/PlYW1sOssnGfoO9TvqMNipi09ChPBuHHzt9PSql5qM9/JvmcvjgDoFHsKrnrQArMWYliST1JPWkx7UdPpQelAFizvJLSQGNsA9QehrSEdvqHMeLec/wH7p+npWNEPmFW1GMUASzWr27lZFKn3703b7cVdt9QbZ5c6CaP0PUfQ1I+nrKpktW81e6H7wpAUMcdKMEYNSFMHB4NAXmgCT/AD0op+P85opgcuaTnHWnkA0nSmA3BP1pMcU7rQRmgBMUm2lAFOxSAbjNGKdjNIaAE+tIRx7UpppFACU0gU4ikIxQMTv60maU9aT8OKAE605U9aaGAzUgYN3oAC4Woi5bpT3jOfWo8ZzQMByaX8qKBQMKKO1LQAmOOtKKTrS4oAOtLg9aAKdQAm33o5oxk0ooAMGlA60uOaMdaADkdKXBoFLQITFKKMZoxQA6j9aMUoFACgYpRSAU4UAGM0tJgUvY0CA4ozSUqoXOByfQUAJR6mr8GmZGZWCD0HWp/stovv8AU0AZNBzWt9ktG46Z9DUMulk8wuHHoetAFAfWlx+FK6GNirAqR1BpAKAAdKXbz60nanD9KADBpcGlIopiEowaUUdaQCAflTgMigD1petACAU7vSdxSqKAHfhSHpS4ooAT6ijJFFJ0oAfFK0LB0Yow6MODV5r6C/G29TEnQXEYw34jvWd+FJmgCe60ySFPNjIuIP8AnpH2+o7VRP8Ak1bt7uW0k3xOUP6GrJNpqOd4FpOf41+431HagDJpOtWrzTprM/vE+Q9HXlT9DVUigDd0XxZeaXtjcm5t+mxjyPoa73SNbtNYjzbygvj5om4ZfwrybODRHO9vIJInaORTwynBFBSZ7Tggdap3+jW2pr+9TEnZ04auP0T4gyJiLUlMi9PPQfMPqO9dzY3cF9CJreVZoz0ZDSKOK1fwzd6fukjH2iEfxoOR9RWTHK8Z4Neqjk81kar4VtdSBeMfZ5z/ABJ0P1FMmxyunat5UyCUny9w3AenermtvC8m63fdCT8pz2rL1PRbvSZD5yHZniReVNVUlIGCeKdyT0PwXzpLc/8ALU/yFW9bUnyfxqn4JbOisf8Apq38hVzWjxCfr/Sky0c7rGEtMHpuFUtN8RHREd7WxtftZ+5dvHudPpmr2sRST2myNSzbhwKoWugliGuGwP7i/wBTQJ6soSyXes3TSyySXM7dXY5//VWpY6IkWGm+dv7vYVpRQJbptRAg9BTzz3phYQKFGAMCnduBQFJHSs/U9attKUmZ8v2jXljQMv5rC1fxfa6fujgxdXA4wp+RT7n/AArmtY8S3eqZQHyLc/8ALNDyfqe9Y2KQrnqfw51O41a1v5bh9xEqgAcBRjoKXx+uP7O9y/8ASqnwmGdO1Ht++X/0Gr3j8f8AIN9y/wDSl1H0OfjiLKMfnS4aNsEFTWjoUN7NN/xLnt/tSrlYbgjbMO688GtVV03Wbg2ksR0DVxwbK7JEUh/2GPT6GtUZNmPZapNaSKyOysOjKcEVti9stckWW5LWl8n3L+1+WQH/AGvUVk6jolxp05jliaJxyFfuPUHvVEkxtzkGncmyZ02oyXUEQbUYReR/w6jaDOf99e31rIexguxmJgGPT0NGn63NaZAY7TwVPQ1bZ4rtt6YjY+nFK4JWMO5sJbdjkHFNjuZYwVDtj0zXRIQ2I5hlTwG9KzdU00WznAxTuVcs+B2zr7nP/LFv6V2OrnFhJznp/OuK8ENjX2/64t/Suz1P5rKTPt/OokarY5K9J8ib/dPf2rhrS7kgcFHZG7Mpwa724hDpIv8AeBFc/baHb2ZycuR3aoQNXK1pay3GWOQD1J71qxRJAM9/eq89/HCNq849KgtIL7XZ/KtYmkPcjhR9TTJ0Ran1RIhhSCal07SL/XR5oAtrQctcznagHt60120bwu4Fyf7Z1TPFvFzGh9/X/PFJqEOoa6Vl8R3x0yx6pp9uP3jD/d7fVqLktkw1iw027Sy8P2b+INXY4E7pujU/7K9/r096ztWt9Ttr6RdXlWS/YBpNrhtuei8cDHpWl/wkY02zay0K0XSLZhh5EOZ5f96Tr+AxWQlu8v3QSfWhAV8VNbQPK4wMjPXtV6DTVXmQ59u1SvdQ2+EHzHptWqGkWycDpXG3rD7ZN/vmuzI9a4u+/wCP2fv85pDZAWxSbs1Ys9OuNRkKQRlj/E3RVHuavhrDRj8gXULwfxH/AFSH2H8VBJFZaLLcRefO62doOs0vf/dHUmp21mLTVMelRGNiMG7lGZD9B/DWfeXs+oy+ZcSNIw6A8AfQdqhxzQArs0jl5GZ3Y8sxyTSEUtHWgBuM9KTkmn9aQ8igBuDSYpe9GMmgAOT3ppp+M00ikCG/jSEZp38qQ80DI8EU+KV4H3xsUYdxSHntTfrQBoC6t74bblfKk/57IOv1FQXWmSwLvGJIz0dORVUg9asWt/PZn923y90PINAEMNlLdSBIo2dz/CorTjsLPTOb1/PmH/LvEen+81Nm12V4vLt41tFP3/L6sfrWb8xPNAjQvNYnvEEQxBbjpDFwv/16p0ylzQMdQTwaKDQAnWj3oxx7UevagB9uMyqOgq6EqnajMy1ohaAGgY9qkjd4m3oSrDuKApI5pwU0gLX2qK84uV2v2mTr+PrUc9o8PzDEkZ6OvSoQmOa09Jsrqdv3S4jPUt92kwtco4orq/8AhHfeP/vmijmRVmeWCjHWg5NGc96skbjpS4p3vTetIBADmnY4pOaKAFxSGjk0UANx/wDrpDQeaSgBKQ9aU5x6000ABpp96U8039KBiYzTc4p+M03GaBjlkx16U/YsgyKh70KSDkcUAPZSvWmn6VKsoPDD8aVoQRleaBkXek7jvSn5c0Dp7UAHcUtHWigApQM9aBg0tACgUtIKUfpQIXHFKOaTrS0AOFLTcGloAXrQaPrS4pAJjvilxx7UnIoHWmA4c/hS/Wm5p1AC+tKKmt7R5+QMKOrHpVtFhth8g8x/7zdKYivDYtIu5z5aepqwjx2/ES8/3zUbyFzliSfekzSAe0rN1JJ96Zycc0tHFABn2p6SMpyOKZilxQBY8yO5XbOuR2YdRVa40541LxnzY/UdaUZqWG4eJsqaBGdjFOHWtV4oL4c4il9R0NUbiyltm+Zfl/vDpQBDRijBpcUAAAFKB1pAaWgAA44paQdKWgAAxSikApcUCFo65oxxRQMOtFAoxxQAn4Uh/KndqaepzQAnWkz1peD1pvWgCza6jLaqUGHiPWN+VNSPZ21/lrZvs8veJzx+BqielIMjpQA2e2ktnKyIVb3qPHrW7p0NzqEbK0PnwL1kfgL/AMCqObRRIrSWcgnUfeQH5h/jQMxwAKtWGpXOlTebaTNC/cDofqO9QuhRiCMEdR6UztQI7/Q/H8F4VhvlFrMePMH+rb/CuxicOMggg8givDiAa1tE8TX2hsFifzYO8Ehyv4elIq567JEkyMkih1bgqwyDXN6p4JjmJksWETf88m+6foe1WtD8W2OtgIr/AGe5PWGQ4J+h71vISDigejM/wrp82naW0M6bH8wnHtxUmtIQsP1Naqk49qz9XTckX1NAIytoxTShxmpRGevah9qIxY7VHUnpQgK5GKgubmK0iMk0ixoO7Vi6141t7bdFZKLmYcGQ/cH+NcdeahcajN5lxKZG7Z4A+g7UxXOk1Xxi8mYrIbE6eaw5/Adq5qSRpWLuxdzyWY5JpgNKaCRjdelNx+FXtO0m61a48m0gaZz12jgfU9q6KPQtM0DDajKNQuxz9lhPyKf9pu9AG58KYWTSr12UgPMME9/lq58QBgab9X/pVrwZqjanbXJKJGkbqqRoMKox0qt8QCCmm/7z/wBKOpXQ5uJyhBBroI9bg1SzFlrNuuo2w4RmOJY/dX6isFIC65HT1prBkqyLXOutRfafaFLY/wDCUaIOfsspxd24/wBn1x7VANMs9ciebRrj7UF+/aSDbPF7EHrWDY6rJZyK8bsjg8MpwRW3JeWHiB0lvla0v1+5qNodkgPbdjrTM7WMW5sXiY4BBBxg9RUaXEkBwfyrev5r+0TdqSLqdsfu6laj94B/tr3+tUWtobxA8bCRT0daRSdxlvfrJgMfzrT1Kz/0C3lSQS7wchf4faueuLKS3OQDt9RSwanNApUH5T29aANDwUCPED/9cm/pXa6lxZS+vH864nwSxPiAn1ib+ldrqRxZyk+g/nUs1ic1LgBjmuVurua9m8qFGbJwFQZJrp5z+7f6Vzegz6j9te301U+0zZAZ8DaO5yelSgkyyNFtdGhFzrlx5OeVtYzmRvrUv2rUtds/9HCeHtBHHnNw0n07sfp+dJNbaZoc7TXMq+INYzlmYk28R/8AZyPyrMvtRutWn825laVuijoqj0UdAKRmtSxFc2ujDZpMJST+K9mGZW/3eyj6VVXfO7MS0jseSxySfrVi305nwX4X9atZis1PIH8zTsXoiO208/ekOP8AZqzLcw2owOT6CqLXVxeSiKBGZm6LGMk1De2k1hN5VwuyXGSuckfWqEWjdGfO5ti+gqCbYXXb0zV/wt/Y/wBrmm1qd0t4k3JFGCTK2enH/wBb61Fr+rWmq6osljZ/YrdQECEjLYPU44FFwNPbmuau7K2tbqSW9lLbmLLbxH5m+p7Cup2jNcLfDN7cHrl26/WgbLF5q011EII1W2tR0hi4H4nvVIAUDj2pVwTQIWk70v40daQhDR3oNANMQhFBHNL1oJoAbtNGKXHr1peT1pDGkZpMZpxFJjmgY0ikpcUnY0AJgUm0UpBo70AJj2oIpcUEcUANxz6UYoPWkI55oEB60f40H+tGKBi9/Wg+/FJnFFABmjPFJ0pCwoAsWXNwv41qgVladzdJ9DW3DC8zhI0LueiqMk0mMZt9qsWenz3r7YYzIe5HQfU1vab4TPEl6cf9MkPP4mujht47eMRxII0HRV4qHItQ7mFp/heKA77giaTrtH3R/jWyI1QBQAAOgHFSthQSeAPyrKvddhhJWL943c9hUWbLbUTX20Vgf27J6D8qKvkZn7VHlXWgUHmgjI9q1IHE55ozmm45oxnvxUiuO6+1Jnik6j2oOeaBBuPp+NJnnmk70d6YwJpKKQnNAxM8UhNGKQ0DEzkYo60UZoGN60daU80h5oBCEZopaSgBOlPSRk6H8KZRigCwHSUYI2mmvbleRyKgzipUnZeDyPSgYwjFKKnwkvTg1E8RQ+tAgozRzRigY4E0opnNOH1pCHA0ZxSEDFGDQA4Gl3YpoGRRnP0pgLnNFNzmloAXOKdTQKuQ2JIDSny17D+I0AQRxvK+1QWJ7Cr8VpHBgynzH/uDp+NODCNdsY2L+pppOKYiR5Wk4bAUdFHAphOaTr2o6dKAF60HilFHrQAmKXpSilFIBAMUYpRxRigBSKAKB19KKADvVmK8ZF2uBIncNVajB+lIRYksIrkFrdtrf3GrPlgeFirqVPvVlGK4IODVtbmOZNlwu8evcUCMf+VKDWjcaQSpe3bzV/u9xWcyFWIIwQeh4pjF60CkI5oH0xQA7PtRnmkHalB5oAdn8KBSUZoAWjNJnmgflQAHkCkPvS5pD0NMBMCm7aeqMxwBknsOta9voKwRifUZfssJ5Cf8tH+g7UAZdtZy3cojhjaSQ/wqK110+x0Ybr5hdXI6WsR+Uf7xqG414xRG3sI/slueCR99/qaysluTQBe1DWbjUMIxEUA4WGMYUVTimkgcPGxRx3Xikx+FGKANMX9tqA2XseyToJ4xz+I71WvNElt082Ii4gPSSPn8/SqmKntL2eyfdC5X27GkBQKkUf5zW4TZap/rALO4P8a/cY+47Vn3ulzWRHmL8h6OOVb6GgRVySQehHeuo0Hx7eabtiuwby3HAJP7xfx7/jXLFCKQg0tATPbdG1+z1uDfazCQj7yHh1+oqfUR5kcf1rw2C5mtJlmgleGVejocGtS88Za1e24he+YJ3KKFY/iKLFXO313xRZaECjP5912gjPI/3j2rgNX8RX2tsRM/lwZ4gj4X8fX8azQmCSeSeST3pwFMVxoWnAcUuzdW1pfhme9i+1TutlYjrcTdD/ujqTQBjxxtI4VFLMTgBRkmuksvC8Nkiz61MbWPGVtk5lf/AOJH1p41e00hTHpMOJDwbyYZkP8Auj+GsiSaSeQvI7O7dSxyTQBuXviZvs32TToV0+y6bI/vP/vN3rDLkk5PNNFJmmB33w2x9kvv+ui/yNTfEH/V6af9p/6VD8ND/ol9/wBdF/katfEFMwab2+Z/5CkV0MnQ49S80yabDHdyIPmt5cYkXuMHrWlANL8QTNbwg6Pqg4fTr0lQT/sMf5GudtppLZ1eN2RxyCpwa3pNbsfENuttr9oLkDhLuP5Zk+h71aMmZ+p6HcafM0ckTRuP4WH+c1mlnhY9Qa6tY9W0myBgdfF2gqP9WxxdQD278fj9Kqx2Fj4ihabRpzdFeZLOUbbiL14/i/CkxJmfYa7NaHAcgHqOx+tW3MUz+dbr5Ep+8E6H8KyJ7BkZgBkqeVIwwP0qOGZoH4PNA7djeiu0clLhNrZ+8OhqLUNJib54flz+IqrDeRT8ONp9a0ntWgtBKJA6Ht6UxFTwa23X8f8ATNq7PUmJs5e44rhvB2W8RH/rm9dvqK4s5Salmq2OauDhH+hrh2Yh27HJrt513KR61gpo0cLGSdww64PAFSgZRtbWSfoML6npWmkENmoZ2GfU1XuNVjiGyBQ2B1xxTdP0m+16UmNSUH3pX4RfxpkjrjVs/LEPxq1aaFIYPtupzjTrLqZJfvN9BS/2lpvh+ZbbTIf7a1c8CTGY0PsO9JcaT5k4vfFd69xN1TTYGy30PZRSuAQ6zeao76f4SsXjj6SXrD5yPUseFFZE2nvps7QSXcd7KPmeSJiw3HqN3etTUPEE95bizto007Th0tbbgH/ePVqrW2kyS8keWnqaaGikck8VfstKlkZXkHlp156mtK3sobQZUZb+83Wknv8ABATknvTA0Bya4a+/4/Z/+ujfzrvVHSuCv/8Aj+uP+ujfzoKZDQBzSA5pc+tBAoHFFFHWkAZyaD+lFFAhKCM9qDzR+NABmjPWikIpAIaRuvWg0Y6UxoOtJnr2pccUhHPWgYlHegij60AB5pD0paG6UAMozzRkUmMUABoNBFIaADgUh+lBPWmk8UAKTSE4FaGjeH77X5dtrCTGDhpn4Rfqf6CvRdA8CWWjBZZv9Nuhz5ki/Kp/2V/qaTdi1Fs5Lwr4QvL+VbmZDbWuOGcYZvoP616DY6ZbabHtgj2nux+8fqavlOuagubiK0jLyuI19TWTbZqoqI7ZnoOKqX+oW+nL+8OXPRB1NZOoeJ2cMlqCi93PU/4VgSytK5ZiWJ7mqUL7mUqlti7qGsT35Iz5cX9wf1qmi5Ip0ULSsFUEk9AK000+OzAe6b5u0S9fxrTY5XJvcqeX9aK1vtK/8+a/n/8AWoqrknk2aKTOc+tFSdAEjNID+FL1pOtAwzxRxRj1pCBQAEgfWkzQQDTTQAE9aTrRmg0DEoNBpPwoGFJ3oJzQTk+1ACdTRikzzR+FA0LQaO9FACEflQQM0UpoASijFBwaAE3YqeO4wMNyKgIzRjn0FAFoxJIMoeahdGXqMU1WKnI45qys6v8AK4/HFIRX+lAORVhrYMMpyPSoDGVb0pjFHNKDTSo7/nS44pAHpilpMVJDC87bUXcfamA2p7e0efkDCf3j0q3FYJDzJ87/AN0dKlZs9eg6AdBTENhijt/uDc/99v6U7JJJJJPcmkzzxSZoELupOuaTOaPbrSABilAoUE/4VPDayTvhFLn0ApjIsYzS4rRGiXeM+Q+KqSwPCxVlKsOxpCI6Uc0mKUYPNABil9+lJ/Kgc0AGM8UcUYzS4oEFJR39KUDigA70gNLtGKMAigB8U7QtuRiDVtpLe+GLhdknQSqP51Q20tABd6XLbjfjzIuzryKpEYrWtrt7c/Kfl7qelTPaW2oAlCIJvT+E0AYffml6VYu7Ca0fbIhHv2NVjkdqAFz7Uuabmk70AOzRnNNySKs2dhPfS7IYzIe5HQUAQj2rRsNGlu181iIIO8snA/Cp9llpH+sK3l0P4F+4p9z3qje6nPfsDK52jog4UfhQBpnVLPSRssIxNP3uJB0+grHubmW7lMk0hkc92NQ9TS4HGaYC4B7UoApMetOAzSATA9KXH4UYFGAeaAExRSnBpMDvQAh49hVu01OW1UpkSQnrG4ypqqQDSbaAL7WVrqHNq/kTHrC54P0NZtxayWzlJEZGHY96cODwcVeh1IPGIrpPtEQ4GfvD6GgVjIxmjGSK15tHWWMy2b+fGOqfxrVGG0knlEUcbPITwqjmgZWCk1f0zRbnVZfLtoi57t0VfcntWtFotppKiTVJcydVtIj8x/3j2qK/1+a7i+zwqtpaDgQxcD8T3pgW1i0zw/1C6pfL2/5Yof8A2asvUNVudVm8y5lLkcKvRVHoB2qqaTvnGKAFH5fWlFJmgE0AOFJ70YJIrf07wvK8Au9QkFhZ9Q0n33/3RQB0Hw0H+h35/wCmi/yNWPiG2IdOGf43/kKt+ELmylt7mOxhaOKJgCz/AHnODyap/EI/uNP/AN9v5Cp6ldDl0UsBg80MrofmBHvVzS0vdzSWVrHesi5e3kAIde4x/hzWhbNpuuOYbR/7N1AcNp162Ax/2HP8jVENmVY6tcaZMJbeVoZB3U1tyT6Z4mkSa6zpGrIcpqNr8uT/ALX+fxrMvtGktJTFNE9vMP8AlnIMfl61RZGhJyCMdqdybJnR31xdWu1fENv50Z4j1qyGQfTzAKpzWMM/CSLJnpInRqg0zXriwyiPmI/eiflT+FaStZXzB4MWcx6r/ATQLYwLmwltWJwSPWnR6hLFGYyxKn+E9K32GxvLlUfnkGs/UtJj8oyxHHqM0DIvBb/8VEv/AFzeu51M5s5fpXCeClx4jT/rm/8AKu51MYspfp/WkzRHMzNtBPWuVme51i++zwq0jsxCRr3rprnHlt9K4+0he4v0ijuUs3dsCeRiqp7kikDN99O0nwuok1m4Fzd9VsLc5Of9o0t1JqWv2yPqEi6Dop/1dtGMPIPZep+p4qKIaP4cJazH9r6l3vbhf3aH1RT1+pqhPcz6jcGSaR7iZv4mOT/9ap3JLo1SHTIjBpFv9ijPDTtzM/1Pb8KpQW8l05wCxbku3+NXrXSeA0v12irrTQ2q84UDtVWHYba6clvgnDN61NLdxw8Dk1QN5PeyrDbozM5wqqMsadqOl3ejzJFeRGKV1D7ScnB9aaHcc0rTk5OB6VDKRvUD1rS8LSaT/aDPrEzRWsabgqqSZGz04qLxLq9nq+siWwtzbWqhUVSAC2O5x0ouSayDgV59qHGoXI6fvG/nXoa8CuVubTTdVvJ4oZzp+oq5BS4P7qY+ob+E+xoKZz+fXilqa+srjTJzDdQtBIOzd/cHuKgzSEPopPrS5zxQIMUGjFGKAA0nU+lLjNIRmgA4+lNJzS7f50mO9AAeaDRgUYzQMaT2ozzigijAzQIQ9KBRgGnfWgYmKQ0tNbIxQA04ooPpSHpzQAH6Uh9aMmkJGKAGn1rp/Avh6y1u6me9YmOHGIs4Dk+prlyea67wGMrefVaGNHp8FvHbxLFFGsUSDCogwB+FSbPasK21Ka1wCfMQdm/oa17bUIbsYQ4fuh4NZtWOhNMfOhZH2EKxGAxGcGuB1eG9huT9s3Mx6P8Awn6V6CwzVa6t454ykqB0PUMKE7EyXMedK3b1p6jJre1DwwAS9s2M9UY/yNY72zwOVkRkI9a0vc5JRaLdvfi1gCwIFmP3pTyfwqW1kRGD7ftFw3O6T7q/41nqOcip4wd1MzZu/arr/n5j/Sis3B9B+VFOzMzyoUdaWjOak7AzR9aM0nJNAAelIaM+tDH2oAaeaKKTPtQAdaTmg89fyozx6UDE6/SjrR9RxRg5oGGPak/nS/5zSHmgBDz9KAM0tGKADFHUUUGgYnWl9+lJ2oFACkUd6MUdaAE69sUHmjr9KDQAUuePWkzSE/lQBJHMYzwfwqys0c4w3Bql1pyqaALD2zKMryKasTMcBST6VashInJ+76GteAQMvyAI565oEZltpfG6U4H90dauZWNdqLtHtSzsFJqDcT3piFYk03GRTSaDkjpQOwdBRyf8KACTU0Vs8hxigdiILnpU0Vs0hwBmtWy0V5CC3ArbtdOit8YUE+ppBYyLDw+8pDS/In6muitLKK1QLEoGOp7mngcVIgPFIdh6rmobzSodQjKyJ83ZwORVpEqzFHxQM871PTJdOnZHHHVW7EVQIxXo2vadHd6dIW4ZBuU+leelfmNMgiz7UoqQRZFauneG5rvDy5giPOT94/QUAZUUTzOqRoXc9ABkmtyy8KSyANcyCIH+BeWrfs9PgsE2woF9WPJP41a+gpXKS7mL/wAInZ7fvyhvXd/9aqF94UniBa3cTKP4ejV1NOFFwsjzmWF4nKMpVh1BGDUeK9DvtLt9QTEyDd2YfeFcxqPhq4s8vEPPi/2eo+op3JasYmDjpTh3pWBBOeDSAZzTEABp4JFNA/8A10ZNAF+HUCE8uVRNEezdqiuNGjuhvtHBPeNuD+FVgT/+unpIyEEEg0CM+W3kgYq6lWHY0RwvM4RFLOegUcmt0XqXKbLqMOOz9GFTTLJZWh/sxFII+aXq9AFGPSoLBBLqMm04yIE5c/X0qG71ySWPyLdBa2/TZH1P1NZ8hdpGZyWc9Sx5plIB2c8Cik60uM0wFHFLikFLn1pALRR3oHTigBaKKM0ALSfWl+tHfnimAmKPw5pT06UhGaAExxSGlo69aQDop5IHDxuUYdxWk3iW8EJWNY4JGGGmjXDt+NZVHfrTAUlnYliWY9ST1oGe9H1o60ALSHJo7+lTW1rNezLFBG0sjcBVGSaAIhzWno/h+91uQi2i+RfvyudqIPc1dj03T9FAfUn+1XI5FnA3A/32/oKr6n4lu7+MQAi3tF+7bQDag/xoA1xNpPhcf6OF1XUVH+ucfuYz/sjv9awdR1a61W4M1zK0rn16D2A7VSL5pM0Ad98Nmzb34/20/kan+IP/AB7WJz0kb+Qqr8NGzBfjP8SfyNdTqFnBqNuYLmISx9RnqD6g9qnqWea213JbOHjcow/iU4IrafULDxFEIdZg3uOFvYuJU+vrRqfg24td0lmTdwj/AJZn/WL/AI1gcoxxlWB5B4IpmbR1DHWNDswGC+KdCUcZ5miHseo/X8Kjt4bDX4y+kz+eRy1nN8syf/FD6VlabrNxp0oeCVo2746H6itC4h0rxFIs0oOk6kDlby24Un/aFURsZ91YPC5+UgjqD1FQpO0Rwe1bN1PqOmKq63b/AG626Jqdrycf7WOtVntre7QPBIsyHo6f1FA0xsGphgFkOR61r6hHBLowmhbLLgMAetczPaSQEkDK+oqIXEkasoYgHqM9aB2NLwa2fEqf7j/yru9U4sJs9Mf1rgvBRz4kiP8AsP8AyrvtTANjN9P60mWjkrpv3T49K4dj+9bvzXdzReYhX1rITSraxYyyHc3XL9BSGzOstNlucMw2J6nqa14oYLBM8L/tGqc+s9VgXPbcaTTdF1DxDcFYUMgH3pXOEX6mmTdIddayTxCMA/xGr2m+F7m9h+2ajMunWAGTPccEj2FSLd6R4XuFtrOI+IddJwFQZijb2H+fwo1LS5LyVbrxfftI/wB5NIs2+7/vEcL/ADqSGwj8X+TMdN8E6Y97dHh7+Rcn657D8qyr9NQt58andx3l8RukaOTftP8AdJ9fpV678RTNa/YrCKPS9PHHkWwwW/3m6ms+20ya7OEXCf3m6UDVyozE4zWjpulSzursNkYOcnqa1LLRYbXDMPMk9WHH4VpBelUXbuOUYHNeb64MateD/pqa9Jwa8314/wDE3vP+ujUDZPp/iOa3txaXcYv7Af8ALCY8p/uN1U/pVptIh1FGm0iYz4GWtZMCZPp/eHuK5zNPikaKRXRijqchlOCPxoILjKyMVYFWBwQeCKQGr8eupqKiPVIvNboLqMYkH1/vU2400ovm27i6g/voOR9R2pDKgbJpc0gANL1PNAgzn3pCfxpeCKQ0AGc/hSdSaU80e9AxMUlKeaTPWmAGm4pc0nNAC0fhQaM5FIApDS5NNYn8KAEpGooJ/CgBv6UhPWlprdSaAG9K6/wE2FvPqtcea6fwPdRwSXEbsFL4xnvQNHbhd3uBQYSCCOCOhFPhZeM8jvitqaGwuYN9uWilH/LJuc0BczbbVZITtmBkT+8PvD/GtSOWO5j3RsHHtWdd6fLbNiSMrnoexqmFkt33xMUb271LiUpm08Y9OarXFjFcptkQMPT0qO21dXO24Hlt/fA4P+FaIAK5Ugjrkd6h6GitI5m88PSQkvATIv8AdPUVnBNj4YEEdjXbEcfSqV3p0V199Bu/vDg1SkZSpX1Rh/L7UVrf2AP7x/Sir5kZeykeIHmjGaTBNGOPamWL19KTrTee5pcE9aQBjp/WkPP4UmOKTH50AKaQ8E+tJjikOc9aAFxnFBH+TSYJoxk0DDbS4puPypSPyoKEPNGOaXBNBHSgBOlAoBNHWgQuKQ0opOaBhSDrRn8qM8UAL1oJ9qQ0hoAUnrSZpuc0o9aAFzxRj3p0cZdsKMn0FXksVjG6U49hQCKsNs0x4HHqavJbRw8k5NNa42jag2ioixYck/jQMsPP2FRGQ8nNR7fU0mMg9hQKxaS4MgAJ/GnA5qkh59vSryIWxzQSLtyc09YixqWK2LEVr2el5wz8CgopWemtMwyOK37TTY4QCRk+9SRQrGuFGBUoOOP50hkqqAOBUqjkVCp/zmpF64oGTKKlQfhUAPbH41IJMDJ5z3oAtIMVKrhepqk1wFHWoJL0joeaQg8S6ottYNGPvyfLXI2VhLfviJPl7ueAK6C6tE1GZGmyVXovrV+FFjjCooVR0AphuVdN0SCzw7gTS/3mHA+laZ5pinsakUg9qQxBTgM0u3NSBAB70DGbc0oXmpNtJt/KgY3b2pwFGzvmloEZ+oaBa6iCxHlSkffUfzFctqXh+508ksu+Ls69P/rV3HfrmkJ7HBB6immKyZ5qVIPPFJt5rtdQ8NW16C8B8iU9v4TXL6hpNxp8hWWMr6N2P4073M2rFTAPFA4+vpTGQr7U0BjQImB71NDcPC25GwfaqwBxyRTwDQBfdLbUl/ejypv+eijg/Wsu90qazJJG6M9HXpVhM5/GrkF48HH3lPVW5FAHPlSKT61vzabbX+WhIglP8B+6ayLqyms32yIV/kfxoAhoz7UEYNAOT6UALmikFKOnIpgL+FLikJ45ozk0gFozzRRzQAY9aXFNPuaPqaYC4oxzSEHNAHvQAuKMUY45NJigBccUYpMUvJoAMZrpNN1q3ew+wsf7Nfp9phH3/wDe7/lXNAHNKD60AaWo6VPYje4Dwt92ZDuVvxrPbrn0q5p+sXOmErE4aJvvwyDcjfUVorZ6br3/AB6SDTb4/wDLtM37pz/st2+hoAwTSZ61PqFhcaXcNBdQtBIP4WH6j1qqW6UAbnhjxMfD127NH5sEoAdR146EV6ZperWWsweZazCQd16Mv1FeKlvzqW0vZrKdZreRopV6OhwaVh3se5qoGMcYrN1fw9ZayC0qFJ+gmj4b8fWuY0T4jLIFh1NdjdBcRjj/AIEP8K7OF0uYlmhkWWJvuuhBBoGeeav4avNIy7L59v8A89Yx0+o7Vmxyle9evJGD178YrD1bwTa326W1xazHnGPkb8O34UA0cppfiC50/iN/kPWN+VP4VZnFjqEnnW0QsLg/e8rhT+FZmpaTdaTLsuITHno3VW+hqskhQjBwaq5lymwjsjCOcc9nHQ1DeaYu0unynr7VFBfE4EnK+9dBeWdv/Yy3NvKXAADgnoaB7GJ4LXHiOL02P/Ku81If6DN9P61wXg0/8VJFz/A/8q7jUyfsU/Xp/WkzSK0OeZePWuVu/N1G9ZEDSHdhUXk/lXTFiEPrXNaPcypqgEN9Hp0jkqLqUfKnueDSCRqjSdO8NRLca/PiQjKafCcyN6Z9KtXL6lrlojX0i+GdBI/d2sQ/fTD2HU/U8VRFzpHh+ZpbFm1zVjy+p3q/Ip/6Zof5msue8n1C4Ms8r3Ez9WY5JosZWua41e30uBrbRLUafCRhpz808n1bt+FZ8FvLeSlUDSOeSev5mr+n+HpJ8PcExJ/cH3j/AIV0VvbRWqBIlCgelBcYmRZeH0iw853t/d7CtQIqjaABj0qZjkVEwyaZpaxG2AfemmTP+NZ+ra3a6UuJX3SdREnLH/CuM1XxFdaoSufJgJ/1aHr9T3oE2dTqvi+2sd0cH+kzjjg/Kp9z/hXE3E73U8k0hy8hLMegyahFOHNIm4uPWlA60qrnj8q3LTw4Y4FudTmGn2x5UMMyyf7q9fxNAjIt4JJ5FjiRpJG4CoMk10EFnDoG2S8nYXfX7LAfmH+8egqKXXFtomt9Kg+xQkYaYnM0n1bt9BWUOSetMCze3f265ebykh3fwRjAqvSj8qOtIANLR3NJ2oATqKMUEEikPNMAxmkI96D+VIRyfSgBMUd6TH60YoAcBRikK4PNKRmkAYApCKMGkOTxQAhFIetKRxSEGgBpFIe9KRxSHjPpQAzvXReFNDXVYrlmcxlCApUdDXO13nw8iL2N03X94P5UMaAS6hoDBZ1Nxbj+Nef/ANVb2m6xBeqDG4yOx4NXWjBXBGQex6GsS/8ADaFvOs28iXP3f4T/AIUrhY6611U/Ik376AHlG5zUeqRWgkRrRiyMMlT1U+lcbDrNzp8ghvI2Uj+Lsa27bUI51BVhg9waoVh8sI9OKjhuJ7I5ib5e8Z5FWCwbA4PvTWjHQdPWlYE7Mt2urRXHyn91J/dbv9DVrNYU1qGHSn217cWjKrZmiHr1H0qHHsbKR0272/SiqP8AbVt/t/8AfNFOzKueAUZ4pKOtUc4cf/roGKQik+tAxSPwpM9aDzSHkUABpM80uOvAppGaAQo5+tFJR1oGFLTcetOxQMMUlFL2oATBNFFB96ADqKD3oNIec0AJRRmkyT9KADNB+nFFTQWzynpx6mgCIKTVqCyLfM/yrUqpHb9Bvb1pGlZ+vT0oETb0hXEajPrUTOzn5jTKXigaF69aKQZzR1oGHBpCeDmgjpRigAQZYfWtyw097gjC4Hqam0vQo0VZJ/mfGQvYVuw7UwoAAH4UAR2unJbgcbm96sBcU7cCcdqWkAq8/jTwvBNNFPXpQAgXHSngAnFAIA4qN37ZoAmZwuf51FJOR0NQySEjHrUWSTmgLkhnY0qMWIzTVHOKkRPbrQIliGe1WVGB0qKMYPFWE6Z/SgpDlH5VKAP8KYvOad9eaBkinIx2p47A1GuKmHNILigA0ppUjMj4UZ+lPlheI/MpX+tAEJ4pp+brTyuDk00g/jTAQp0xSEcDNLg56fSgjd7GkA0cYx1qQhJkMcyLIh6q3NIFxmgrnpQBg6p4SWUGSxbn/ni5/ka5me0ktpGSVCjDqGGDXoqKRjtTrmzttSi8u5iD+jdCPoadyHE8zxRium1XwhNbhpLb9/D1wPvD6iufeAoxBBGKZJGvXkVID2pgXFOBwaBCgkH+tXI7wOnlzoJYz2bqKpjvRn8qAFutEEoMlm29e8bH5h9PWsl4yjFWUgjqD1rYjmaNgVOCO4qxJJBfrtuU+boJF4YUwOdozWjeaNLApkiPnxf3l6j6is4jHWgBRSg5pmT6Uo/SgB+cig00Gl9jSAAc0tNHNL1pgLxRmkxk0fXrQAp96P5UdRRjNAC/rR70dvWjGfpQAhyT3ozzSnrSYzQAoajAI6UmKOtAGvZ+I5Y7ZbS+iXUrEdIpj8ye6P1H8qJvD0OoI02jTNcgfM1pL8s6fQdGHuKx84pVdonDoxRwchlOCPxoAgcNG5R1KsDgg8EU3dXQDWYNTUR6vCZm6C7i4lX69m/Gq174clihNzaOL+z/AOesPVf95eopAZW/860dH8Q3uiS77SYqpPzRNyjfUVmshpvINMD1rw98QLLVdkNxiyujxhz8jH2Pb6GuuRwPT6188K2RXR+H/HF/oe2It9rtRx5Uh5X/AHT2/lSKuewzwxXURimjWWNuqOMiuR1nwMPml05vcwOf5H/GtfQfFNj4gT/R5ds+OYJOHH+P4VqsSD04oGeSzwy2szRSxtFIvVHGDQJ5EQqrkKeoB4Neo6hpVtqsWy6hEno3Rl+hrjNZ8G3Nhuktc3UHXAHzr+HemmTYz/BhH/CSQ/7r/wAq7vVRmwmz/drhPBqkeJIR3Cv/ACrv9SA+xT5/u0MpHKOvyN06Vw7Jtds+prvGUspXHWsyz0CCB98v75+uD90fhRsDRj6bo89+QQPLi/vt3+nrXU6fpdvYL8i7pO7tyTUqjjGOBT9xB9qBJJE+4bR603f61E8oRCWbCjqScAVzGr+N4bctHZKJ5OnmH7o/xpFXOmvL+CxhaS4lWKP1Y9fpXG6v42kud0diphj/AOerfeP09K5y81C41GUy3Epkb36D6CoQOaCLjpHaVy7ks55JPJNApQuatWWnT38wigiaWQ9lHT6+lAiqAa0dO0ee/UyfLDbr96eU4Qf41qQafpukSKb1/tlwDzDDyifU9/pS6pbXN+PPgl+12o+6kYx5Y9NvamA2PULPRsCwjFxcf8/c69P9xe31NZtxdS3czSzyNLK3VnOSaiI60fWgB2KcKaPenCgBcZoo+tGelIAz7UUh96M8UwA0lBpPx60ABpOtHaigA+tGO+KTgnmjHNACjilPvSY+tGKAAmkJoxzRxSAQ00+1KaTAPamA0jIoOfrS4pD3pAMP513/AMOGC2FyuRzL/SuAP5V0XhLV200yg8xswJoGj08QrKQu7a5IHPSmXdlJatiRcejdQfpVKw1WK7jDJICa2LXUDE3zgSoRja3IoHexjXNrHcRlJEV1PZqwLjRp7BjLZOWGeYmP8q7Y2C373DW+ECjcIz3FZbR5OMfnQK6Zg2Wvgt5coMcg4IbrW5BcpKOoqlqGkwXy4kT5h0ccMPxrJaG+0hsqTcwDuPvD8KYrHU7N9NaEH/8AVWXYazHcAYbnuD1Fasc6yEc5J/WkPYk8gf3aKn4/u/pRQO/meCZ9eKMg0h560mPWgkXI7ijcPSk780UDAsO9IWoxSfWgAyKTIPXiijrTGGc9f0o5PWkH0ozSAWjvSZJPSg0ALyaM8UnJxRnNAwo60nWjrQAE0h60ZzSqhbgAk+1AAeadHE0hwoz9KsxWYAzJ+QqUyBBhBge1AhkdqkXMh3H0FOeckYHA9BUZJY0nWgYpajPNHFHb0oAcCPwpcgU080oHPtQAuQTRkelGMHpRjPNA0A5p0Y3TRj1YD9abjipIAPtEX+8P50Adgp54GDUqljSKAPcU/tQAqMBwetSqwIFRZzSh8UCJ+1LuFVmnFJ5ufpS2AnaWomkOetMaYZ9KhlnVOpyfagCYvQrh2Iz+VVo0muzx8ifrWlbWKxDAGc96YAkRNWY0/AU5Y8VKFwKQDAlSLxRil29eKChQf/109XXGPSo88nripI4SULuViiHV34FMVyVfarB8u2TzLmQQp2B+8foKyLjxDFb5SzXe/wDz2kH8hWPLdSXMpeR2dz1JNNRM3Oxv3niQlTFaL5Efdv42/HtVWy12e0BGfNiPWN+Qayc80/oD6VdkZc73Ottry21FcRN5cp6xOf5HvSyRlGIIwR1Brkkcgitiy1+WMLHOv2iLoNx+YfQ1PL2NY1L7mmRzzSYzgGrFv5N+m61cOR1jPDD/ABpGTaeRg+9QaXI9nA45pQOadilC0hiqBTiMjpTdhpQD64oAdG5Q8GorzQ7PV1JkQQzHgSJ/WpADmpUO2gDidZ8K3Ol5Yr5kJ6SJyP8A61YbRFSQeK9bS4wuGAZTwVNYuq+FLXUCZLUiCX+4fun/AAqrkWPPNpo/StTUdGuNOkKTRlPfsfoazmQimIaOaM80hPrSbhQInhuXhOUJFSTW9pqJyQLeY/xL90/UVUzmngYoApXumTWTZdPk7OvINVDgV0lvdsi7GxIh6qRkUy40OG+Be0Plyd426fhQBzpIFKCKluLOW2cpLGUYdiKh2GgBwYd6XcMUm3PGKMcUALkUmRRRQA7PPSjIpM57UUAOoxSZz9aWgApCM9aKXrQAmPWiik780AGM9aOaP880ZoATnvVix1C40yYS20zQyeqng/Ud6rmg8UAbn2vTtbOLtV067P8Ay8RLmNj/ALS9vqKzNT0W40x1MqgxtykqHKOPY1bt9CcQLc30gsLY8qZB88n+6vU/WrMWvJYx/ZrS1V7LOXS5+Yye59PwoA5ogilBx25rpDpNjrXOnS/Zrk9bOdsZ/wBxu/0NYt3YTWUzRTxtDIp5Rxg0ARRytHIrqSjqchlOCPpXaaB8S7i02w6mhuoRwJl/1g+vr/OuI2Yz6UZxQPY9503VrPV7YTWc6zoeuDyp9COoq0GAOf1rwKx1C5024E1rM8Eo/iQ/z9a7/QPidHKEh1VBE/QXEY+U/wC8O34UirnajSrM3q3ggQXIBHmLwTn19aXUFBsp8D+Ampba5iuYllhdZYmGVdDkGm3wzZz9vkNIo5YIKDGDnFSlcdqo6nq1rpMRe4mCZ6KOWP0FMCfA9KyNX8S2WkAqzedPj/VJ2+p7VzGseMrm+3R2ubaA8ZH32/HtXPbSTzkk0EXNHV/EF3rBIkfZD2iTgf8A16zQuO1PCY68U9Y8/wCJoJGBc1LHC0jqqqWYnAUDJNath4dlmgFzcutlZ/8APabgt/ujqTVz+1YNNUx6VCYm6G7l5lb6f3aAI4NAisEEuqymDIyttHzK319PxpbnXHMRt7ONbK1PVIz8zf7zdTWa8jSOzuWZ25LMck0zdTGPLU+2u5rOUSQyNG47ioKUflSEbIu7LVsC8UWtyf8Al4jHyn/eFVr3RrixG8gSwn7ssfKn/Cs8Gr+n6rcaef3b5jPWNuVP4UAUzilzWz9nsNXyYyLK6P8AAx+Rvp6VnXunz2EmyeMoT0PY/Q0wIAQaXIzTTx1oPvQA4nNITSdzmjFACZo3DFGKaaAF3DFGRnmmnr0oxmgBxI/CjIplLmgB2aM02g0ALmkPtRn8KSgA68UHilpKAE/CkP0pTSHvQAwiuk8IWqXIuQ43Djg1zeM11ngcfLc/UUmNF+XRZrRvNs5CCP4TVqx8TNGwhvFMbjvWsqBlHNVrzTorlcOmffvSH6GnaagQyywy4PZlNO8ze5LHluciuUaxu9MJe2cvH3Q9at2OvrIdkgMb91PFO4joGG7GDikMYIqKC6WQCrQYMKAMa+0OG5beg8mXPDpxn6iqCT3elOBcLujzxIvIrpimTTXhDghlBB9aQFP+24vU0VZ/sa1/54L+VFMXKeHZ9qM+1X/7B1LOPsM//fNH9haif+XGf/vmnYZn0Z9q0P7A1Hr9hn/74pR4f1Jv+XC4/wC+KLMDN70hrS/4R7U/+gdcn/gFH/CO6p/0Dbn/AL4oswMz8KK0v+Ed1Q/8w25/74o/4R3Ve2mXP/fFFmMzTycdKBWn/wAI5qv/AEDLn/vik/4RzVf+gZdf98UWYGbQTzWl/wAI7qv/AEDLn/vig+HNU/6Btz/3xSswMzPNGOK0j4e1Qf8AMOueP9ilHhvVT/zDrn/vinZgZlLgmtRfDeqE4/s+4Ge5WrcXh29t+TYzM3rt4oswuZMFi8nJ+VfU1aCJAMKMn1q9JpOosf8AjzmH0Wojo2oHpZzZ/wB2iwXKTuTmojkn3rR/sHUOc2c3/fNIdB1DnFlN/wB80WC6M8UVf/sLUR/y5Tf980v9g6gR/wAeU3/fNFh6GeDmnCr66DqB/wCXKb/vmn/2BqB5+xzfXbRYVzOApcGtD+wNQ6fYps/7tO/sDUAM/Y5v++aLAmZ2M0bc9q0xoF/3sph/wGpBoF/3s5v++aLBcyQpqSAYnj/3h/OtX/hH78jmym/75p0fh7UPMUiymGGH8NKwG0DzRuJ9quNpV1t/495P++arSabeDgW0hx/s0BciaUAk5qvLd5PWnSabfnj7LLj2Wq50nUD/AMucx+i0wuO+0bjzT/tKqMk1CukaizYFpNk9yprSs/C9yfmmjfP90A0rBcpI8lydsYJ96v2ul7fmk+ZjWtb6RLCoCW7gey1ZXTbjJIgk/wC+TRqO5SjtwuAOKmWLBx2q2umXJ48iT/vmpU0q4z/qZPwBpWAphKds9uKvjS7nPEEnpjbTxpNyesEg+oppDujM8vPGf0qSO3dzx07k8AVdns5LOPLW00zHokaH9TWHfrq9/wDJ9jmjh7RohA/GnYhySH3erW1llY8XUw/74H+NYl5qNxfuGmct6KOAPoKtf2DfnrZTf98Gj+wb9j/x5T4/3DVpGMpXMzJPGcVIp5q+2gX5/wCXOcj/AHDSjQb/ALWc3/fBqjO5TViOKkD5HTFaFt4dvXcB7aVFPfZVm98NTQgeRDNLnr8hoFcyFJz7VKg6YNWl0K/PH2Kf/vg1PHoN/wBTZzD6oaYrkEEjRsGUlSO44IretNd80BLyPzR/z1Xhh9fWs5dEvgf+PSb/AL4qVdKvVI/0Wb/vg1NrlqTRuC0E6b7dxMn+z1H1FMMWOO/vVC1tr+2cPHBMjeoU1t280txhbq0kVv8AnoifzFZuJupplPGe1NKY5rUk0icgFI2YduMGq76dcZP7l/wWpsaIpBR604HBHFT/AGG4H/LFyP8AdoFjcY4hf8qLBciyQKVHK9/xqUWM+eYX/KnfYJx/yxf/AL5NFhiO8VzEYrhFmjPZq5vV/BiyBpLBt3/TJzz+BrpRYTqf9TID9Kd9jnHSJx/wGjYR5Je2U1rIySo0bDqGFVwpzXr91o41GPy7u1Mi9m28j8a5nVfh9c23720RriI/wgfMP8aYrHFhDnnrUg6c9P51rv4Y1FePsM//AHwaX/hHNQH/AC4z/wDfs1ViTKXg9MVPE5TkZBq+PD1//wA+U2f9w0o0O9UHNrKP+AmkMRbqK7j8q8iEydj/ABD6GqV34WZ0aWwf7VF12dJF/DvWh/ZF2o5t5P8Avk1JBZXkDh0ilRh0IBFVqI42WBo2IKlSOoI5FRbeeteg3FiNXG29tXSU9LiNcN+PrXOal4UvbOX5IWuIz0eMZz9fSgRz7DmkJ71otod+P+XKf/vmozod/jH2Gb/vilYLlHr3o7dc1b/sPUB/y4z/APfFH9iaj/z4z5H+xUu4ymGyadwatHRNRP8Ay4T/APfFJ/YWpAZ+wz/98U7MRWPvQT3NWhompA/8eM5/4BS/2HqPexn/AO+aLMZTJNLnJq2ND1AdbGb/AL4pw0S/zn7FN/3zRqK5UpcVp23hzUrqZIks5AzHqwAA+prdGgw6CoL2zape9doH7lD/AOzU0hnP6foNzfoZsLBaj71xMdqD/H8KuLeWWk8afF9puR/y+XC8A/7Cf1NSagurak4a4hmYD7qBMIo9hVP+yr4/8ukv/fNOwipcyy3UrTTytNMerucmocVotpF8R/x5Tf8AfNN/sS+72cw/4DRYZnf0rYttfd4FttRhGo2oGF8w4kT/AHX6/gciqzaNfA82k3P+zSjSb0f8ukv/AHzRYCWfQY7xWl0qY3aDlrdhiZPw7/UVitGVJBBBHY8Vqppd8jh0t5kZTkMoII+la0dvNq2I9Ts5N54W8jXEg/3h0YfrSsByJHNBPHSt3UfCt7ZSYjT7VGfuyRf1HaqZ0O+H/LnN/wB8UrBcTR/EF9oMweznKKTlom5RvqK7e3+KFncWTpeW0sExGD5Y3Kfp3FcP/Yt9/wA+c3/fNJ/Yl/jP2GbH+5RYdzX1bx3PcbksIfs6HjzH5c/h0FcrM8tzI0k0jSSNyWY5Nao0S+/58p/++KUaDfE/8eU//fFKwGQIe1PEPtWtHoN+xAFlMSePuVuQ+GU0qMS3kDXtwRlbaL7o/wB5v6CnYRzunaHcajuMSARL96ZztRfqa0kfT9H/AOPdF1G7H/LaUYiQ/wCyvf8AGp9QXU7/AAskDpCv3IIk2ov4VSbSb09LWU/8BosIqXt3PfzmW5laWTplug9gO1V8VfbSL0/8uk2P92mHR74/8uc3/fNOwyiaQ5q8dGvv+fSX/vmkOjX/APz5y/TbSAo0oq5/Y19/z5y/980f2Pff8+kv/fNAFSnKatf2Pff8+kv/AHzTho98D/x6S/8AfNAFYHB9q1LLWpYY/JnRbu2PBjk7fQ9qrDSL3vay/wDfNOGlXg/5dpP++aALkmjwX6mTTpMt1NtKcMPoe9Y8sDwSMkiFHHUMMEVopp14rAiCUEdMDkVpqlxeRiK/s5Jl6CUDDr+PeiwHLnpSfhW5f+GLmBfMtwbiI+gww+orPOj3uf8Aj0l/75oApE0hb/8AXV86Lff8+c3/AHzTf7Gv/wDnzm/74oAo5zSVdOjX/wDz5zf980f2Jf8A/PlN/wB80AUfQUVdOh6gB/x5Tf8AfNH9iah/z5Tf980AUqKvHQ9Q/wCfKb/vmj+w9Q/58ph/wGnYClScVf8A7Dv+f9Cm/wC+aQaJqBP/AB5Tf980gKXWg1e/sPUB/wAuU3/fNINE1DJzYzjH+zQBSNJjNXzouoc/6FPn/dph0bUP+fKcf8AoAqom/rxXUeE5EjM0e4BmwQPWuek028hBL2k6gdTsPFRwXDIwZGIYdx1pBc9UtypkTzDiPIDEDkCtC+0xrXY6yCWF8lJFPWuA0vxbJDhLoCRf74611mm6nDceW8biWINnZn/OKNh+hK8PPtWffaTDdDLLtfsy9a7FRp+s3DAE2pK4GcAFs1kXdmbeZ43+8hwaQJ3OSJvNJbnM0PqOorUsNaS6GA3PT3q9JbB88ZFZV5oSyEyRZikz1HQ0DtY3oplYVKOf/rVykWoXOnOEuFJX++K2LTUknClWBBoBG5t+v50VD5lFMZ//2Q=="

function MachineListArtwork() {
  return (
    <svg aria-hidden="true" className="size-full" viewBox="0 0 1137 464">
      <image height="464" href={MACHINE_LIST_ARTWORK} width="1137" />
    </svg>
  )
}
function MachineArtwork() {
  return (
    <svg aria-hidden="true" className="size-full" viewBox="0 0 720 420">
      <SvgDefinitions prefix="machine" />
      <ellipse cx="356" cy="220" fill="url(#machine-halo)" rx="285" ry="194" />
      <g fill="none" strokeLinecap="round">
        <path
          d="M46 331C153 303 178 341 286 309S474 269 656 324"
          stroke="#55d9ed"
          strokeOpacity="0.68"
          strokeWidth="2"
        />
        <path
          d="M58 340C171 315 208 357 315 322S485 286 660 337"
          stroke="#eb6b81"
          strokeOpacity="0.55"
        />
        <path
          d="M80 349C195 333 230 369 332 334S501 306 647 349"
          stroke="#ffc267"
          strokeOpacity="0.52"
        />
      </g>
      <g transform="translate(252 62)">
        <polygon
          fill="#9fb8cc"
          points="0,65 92,9 193,61 101,119"
          stroke="#bee3f2"
          strokeOpacity="0.74"
        />
        <polygon
          fill="url(#machine-panel)"
          points="0,65 101,119 101,293 0,236"
          stroke="#77acc9"
          strokeOpacity="0.72"
          strokeWidth="2"
        />
        <polygon
          fill="#19344d"
          points="101,119 193,61 193,235 101,293"
          stroke="#7199b4"
          strokeOpacity="0.65"
          strokeWidth="2"
        />
        <polygon
          fill="#122942"
          points="60,38 97,17 140,39 103,62"
          stroke="#8bc7d9"
          strokeOpacity="0.74"
        />
        <polygon fill="#46c4a3" points="73,37 99,23 128,38 102,53" opacity="0.86" />
        {[0, 1, 2, 3].map((row) => (
          <g key={row} transform={`translate(0 ${row * 36})`}>
            <polygon
              fill="#07182c"
              points="17,91 83,126 83,149 17,113"
              stroke="#7399b5"
              strokeOpacity="0.55"
            />
            <circle cx="30" cy="108" fill="#69e8f8" filter="url(#machine-glow)" r="3" />
            <path d="M41 113 70 128" stroke="#617d95" strokeWidth="3" />
          </g>
        ))}
        <path
          d="M119 136 176 101M119 158l57-35M119 180l57-35M119 202l57-35M119 224l57-35"
          stroke="#6a8ca4"
          strokeOpacity="0.52"
          strokeWidth="2"
        />
        <path d="m104 119 84-52" stroke="#d0f4ff" strokeOpacity="0.4" />
      </g>
      <g transform="translate(102 130)">
        <polygon fill="#1b4054" points="0,30 45,0 91,25 48,56" stroke="#5d97aa" />
        <polygon fill="#0f263b" points="0,30 48,56 48,126 0,99" stroke="#5d97aa" />
        <polygon fill="#18364b" points="48,56 91,25 91,95 48,126" stroke="#5d97aa" />
        <text
          fill="#79e7ab"
          fontFamily="Arial, sans-serif"
          fontSize="55"
          fontWeight="800"
          transform="skewY(28)"
          x="17"
          y="65"
        >
          N
        </text>
      </g>
      <g transform="translate(512 115)" fill="none" stroke="#91dff2" strokeLinecap="round">
        <path
          d="M25 86c-28-6-28-42-5-50C20 9 59 1 71 27c23-7 44 12 39 35 18 12 10 38-12 40H27"
          fill="#4d7e9d"
          fillOpacity="0.28"
          strokeWidth="3"
        />
        <path d="M40 75v58M55 82v61M70 78v70M85 74v58" strokeDasharray="3 6" />
      </g>
      <g transform="translate(483 288)">
        <polygon
          fill="#96adbf"
          points="0,40 77,0 166,39 86,84"
          stroke="#c2e6ee"
          strokeOpacity="0.65"
        />
        <polygon fill="#344c62" points="0,40 86,84 86,112 0,69" stroke="#718ba1" />
        <polygon fill="#263d52" points="86,84 166,39 166,67 86,112" stroke="#718ba1" />
        <rect
          fill="#67e1ee"
          height="4"
          opacity="0.75"
          transform="skewY(27)"
          width="28"
          x="20"
          y="51"
        />
      </g>
      <g fill="#92eafb" filter="url(#machine-glow)">
        <circle cx="143" cy="335" r="3" />
        <circle cx="207" cy="328" r="2" />
        <circle cx="526" cy="337" r="3" />
        <circle cx="598" cy="350" r="2" />
      </g>
    </svg>
  )
}

function SecurityArtwork() {
  return (
    <svg aria-hidden="true" className="size-full" viewBox="0 0 600 430">
      <SvgDefinitions prefix="security" />
      <ellipse cx="302" cy="204" fill="url(#security-halo)" opacity="0.34" rx="270" ry="188" />

      <g fill="none" stroke="#7895aa" strokeLinecap="round">
        <ellipse cx="300" cy="196" rx="260" ry="67" strokeDasharray="2 8" strokeOpacity="0.28" />
        <ellipse
          cx="300"
          cy="196"
          rx="255"
          ry="69"
          strokeDasharray="2 8"
          strokeOpacity="0.3"
          transform="rotate(59 300 196)"
        />
        <ellipse
          cx="300"
          cy="196"
          rx="255"
          ry="69"
          strokeDasharray="2 8"
          strokeOpacity="0.3"
          transform="rotate(-59 300 196)"
        />
        <path d="m300 29 145 83v168l-145 83-145-83V112Z" strokeOpacity="0.36" strokeWidth="1.4" />
        <path d="m300 55 122 70v142l-122 70-122-70V125Z" strokeOpacity="0.18" />
        <path d="m300 87 95 54v110l-95 55-95-55V141Z" strokeOpacity="0.26" />
      </g>

      <g fill="#91abba" opacity="0.6">
        <circle cx="42" cy="196" r="3" />
        <circle cx="558" cy="196" r="3" />
        <circle cx="216" cy="50" r="2.5" />
        <circle cx="387" cy="344" r="2.5" />
        <circle cx="447" cy="112" r="2.5" />
        <circle cx="155" cy="280" r="2.5" />
      </g>

      <g fill="none" stroke="#8ca7b8" strokeOpacity="0.46" transform="translate(225 121)">
        <path d="m75 0 75 43v87l-75 43L0 130V43Z" />
        <path d="m75 23 55 32v63l-55 32-55-32V55Z" />
        <path d="M20 55 75 87l55-32M75 87v63M20 118l55-31 55 31" strokeOpacity="0.32" />
      </g>

      <g transform="translate(263 143)">
        <path
          d="M37 0c21 14 39 15 39 15v39c0 30-19 52-39 62C16 106 0 84 0 54V15S17 14 37 0Z"
          fill="#476578"
          fillOpacity="0.34"
          stroke="#9ab1bf"
          strokeOpacity="0.66"
          strokeWidth="1.6"
        />
        <rect
          fill="#7894a5"
          fillOpacity="0.3"
          height="39"
          rx="4"
          stroke="#aec1cb"
          strokeOpacity="0.74"
          strokeWidth="1.7"
          width="44"
          x="15"
          y="41"
        />
        <path d="M25 41V31c0-17 24-17 24 0v10" fill="none" stroke="#aec1cb" strokeWidth="3.5" />
        <circle cx="37" cy="57" fill="#263d50" r="5" />
        <path d="m37 60-3 10h6Z" fill="#263d50" />
      </g>

      <g transform="translate(78 103)" stroke="#8ba6b6" strokeOpacity="0.52">
        <path d="m31 0 28 16v33L31 65 3 49V16Z" fill="#425c6e" fillOpacity="0.2" />
        <path d="M24 31v-8a7 7 0 0 1 14 0v8M20 31h22v19H20Z" fill="#7892a1" fillOpacity="0.25" />
      </g>

      <g transform="translate(273 7)" fill="none" stroke="#8da7b6" strokeOpacity="0.54">
        <ellipse cx="27" cy="9" fill="#506979" fillOpacity="0.22" rx="23" ry="8" />
        <path d="M4 9v34c0 11 46 11 46 0V9M4 21c0 11 46 11 46 0M4 33c0 11 46 11 46 0" />
      </g>

      <g
        transform="translate(463 118)"
        fill="#4c6373"
        fillOpacity="0.24"
        stroke="#8ca8b8"
        strokeOpacity="0.52"
      >
        <path d="m28 0 27 16v32L28 64 0 48V16Z" />
        <path d="M13 16h29v30H13ZM18 22h19M18 28h19M18 36h5M26 36h5M34 36h4M18 41h5M26 41h5M34 41h4" />
      </g>

      <g
        transform="translate(76 269)"
        fill="#4c6475"
        fillOpacity="0.22"
        stroke="#8da7b7"
        strokeOpacity="0.5"
      >
        <path d="m31 0 29 17v34L31 68 2 51V17Z" />
        <path d="M17 19h28v32H17ZM22 28h18M22 34h18M22 40h11" />
      </g>

      <g transform="translate(345 350)" fill="none" stroke="#8ca6b6" strokeOpacity="0.5">
        <ellipse cx="25" cy="8" fill="#506a7a" fillOpacity="0.2" rx="21" ry="7" />
        <path d="M4 8v31c0 10 42 10 42 0V8M4 19c0 10 42 10 42 0M4 30c0 10 42 10 42 0" />
      </g>

      <g fill="none" stroke="#899faf" strokeOpacity="0.25">
        <path d="M127 136 205 166M395 161l68-18M141 304l82-60M373 269l-8 81" />
        <path d="M34 384h139l17-17h101M309 367h111l16-16h126" strokeDasharray="3 6" />
      </g>
    </svg>
  )
}

export function DesignArtwork({ variant, className = "" }: DesignArtworkProps) {
  return (
    <div aria-hidden="true" className={`slsg-artwork slsg-artwork-${variant} ${className}`}>
      {variant === "infrastructure" ? <InfrastructureArtwork /> : null}
      {variant === "machine" ? <MachineArtwork /> : null}
      {variant === "machines" ? <MachineListArtwork /> : null}
      {variant === "security" ? <SecurityArtwork /> : null}
    </div>
  )
}

export function CircuitFrame({ className = "" }: CircuitFrameProps) {
  return (
    <svg
      aria-hidden="true"
      className={`slsg-circuit-frame ${className}`}
      preserveAspectRatio="none"
      viewBox="0 0 1600 1000"
    >
      <defs>
        <linearGradient id="frame-line" x1="0" x2="1">
          <stop offset="0" stopColor="#75ddf5" stopOpacity="0.72" />
          <stop offset="0.45" stopColor="#6286b7" stopOpacity="0.46" />
          <stop offset="1" stopColor="#769bcc" stopOpacity="0.66" />
        </linearGradient>
        <filter id="frame-glow" x="-200%" y="-200%" width="500%" height="500%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g fill="none" stroke="url(#frame-line)" strokeWidth="1.25" vectorEffect="non-scaling-stroke">
        <path d="M24 190V54L51 25h228l18 18h493l28 31h480l25-27h209l30 31v127" />
        <path d="M18 246v535l23 24v121l27 27h252" />
        <path d="M1580 245v390l-19 19v130l22 24v101l-35 35h-307l-24-25h-170" />
        <path d="M24 215h41M24 805h51M1308 47h168M1236 944h-77" strokeOpacity="0.32" />
      </g>
      <g fill="#8eeaff" filter="url(#frame-glow)">
        <circle cx="279" cy="25" r="3" />
        <circle cx="24" cy="190" r="3" />
        <circle cx="24" cy="781" r="3" />
        <circle cx="1580" cy="205" r="3" />
        <circle cx="1580" cy="635" r="3" />
        <circle cx="1241" cy="944" r="3" />
      </g>
      <g fill="#0d1a2e" stroke="#85b4df" strokeWidth="1.2" vectorEffect="non-scaling-stroke">
        <circle cx="818" cy="74" r="4" />
        <circle cx="1548" cy="944" r="4" />
        <circle cx="1047" cy="919" r="4" />
      </g>
    </svg>
  )
}
