/**
 * 파이프라인 단계 네비게이션
 * 현재 진행 상황을 시각적으로 표시
 */
import { Upload, ScanLine, Images, Box, Rotate3D, ChevronRight, Gamepad2 } from 'lucide-react'
import { PIPELINE_STEPS } from '../utils/constants'

const ICONS = { Gamepad2, Upload, ScanLine, Images, Box, Rotate3D }

export default function StepNav({ activeStep, onStepClick, completedSteps = [] }) {
  return (
    <nav className="flex items-center gap-1 px-4 py-3 bg-slate-900/60 border-b border-slate-700/50 overflow-x-auto">
      {PIPELINE_STEPS.map((step, i) => {
        const Icon = ICONS[step.icon]
        const isActive = activeStep === step.id
        const isCompleted = completedSteps.includes(step.id)

        return (
          <div key={step.id} className="flex items-center">
            <button
              onClick={() => onStepClick(step.id)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all whitespace-nowrap
                ${isActive
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  : isCompleted
                    ? 'text-emerald-400 hover:bg-slate-800/60'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40'
                }
              `}
            >
              <Icon size={16} />
              <span className="font-medium">{step.label}</span>
              {isCompleted && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              )}
            </button>
            {i < PIPELINE_STEPS.length - 1 && (
              <ChevronRight size={14} className="text-slate-600 mx-1 flex-shrink-0" />
            )}
          </div>
        )
      })}
    </nav>
  )
}
